"""Coordinate scanning, parsing and backlink counting without writing to the vault."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .parser import Link, parse_links
from .resolver import Resolution, resolve_link
from .scanner import FileIssue, VaultIndex, is_link, path_key, scan_vault


@dataclass(frozen=True)
class Occurrence:
    source: Path
    link: Link
    resolution: Resolution

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source.as_posix(),
            "line": self.link.line,
            "target": self.link.target,
            "type": self.link.type,
            "reason": self.resolution.reason,
            "matches": [path.as_posix() for path in self.resolution.matches],
        }


@dataclass(frozen=True)
class AuditReport:
    vault: str
    files_scanned: int
    occurrences: tuple[Occurrence, ...]
    orphan_notes: tuple[Path, ...]
    errors: tuple[FileIssue, ...]
    skipped_paths: tuple[Path, ...]

    @property
    def summary(self) -> dict[str, int]:
        counts = {
            status: sum(item.resolution.status == status for item in self.occurrences)
            for status in (
                "resolved",
                "broken",
                "ambiguous",
                "external",
                "out_of_scope",
                "ignored",
                "unsupported",
            )
        }
        return {
            "files_scanned": self.files_scanned,
            "internal_links": len(self.occurrences) - counts["external"],
            "resolved_links": counts["resolved"],
            "broken_links": counts["broken"],
            "ambiguous_links": counts["ambiguous"],
            "orphan_notes": len(self.orphan_notes),
            "external_links": counts["external"],
            "out_of_scope_links": counts["out_of_scope"],
            "ignored_links": counts["ignored"],
            "unsupported_links": counts["unsupported"],
            "read_errors": len(self.errors),
        }

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"vault": self.vault, "summary": self.summary}
        for status in (
            "broken",
            "ambiguous",
            "external",
            "out_of_scope",
            "ignored",
            "unsupported",
        ):
            result[status + "_links"] = [
                item.to_dict() for item in self.occurrences if item.resolution.status == status
            ]
        result["orphan_notes"] = [path.as_posix() for path in self.orphan_notes]
        result["errors"] = [
            {"source": error.source, "reason": error.reason} for error in self.errors
        ]
        result["skipped_paths"] = [path.as_posix() for path in self.skipped_paths]
        return result


def _read_note(index: VaultIndex, relative: Path) -> str:
    # Recheck every component: a link may have appeared after the initial scan.
    current = index.root
    for part in relative.parts:
        current /= part
        if is_link(current):
            raise OSError("Symlinks and reparse points are not read.")
    return current.read_text(encoding="utf-8-sig")


def audit_vault(root: Path, excludes: tuple[str, ...] = ()) -> AuditReport:
    index = scan_vault(root, excludes)
    occurrences: list[Occurrence] = []
    incoming: set[Path] = set()
    notes = set(index.notes)
    errors = list(index.errors)
    scanned = 0
    for source in index.notes:
        try:
            text = _read_note(index, source)
        except (OSError, UnicodeError):
            errors.append(FileIssue(source.as_posix(), "note_unreadable"))
            continue
        scanned += 1
        for link in parse_links(text):
            resolution = resolve_link(link, source, index)
            occurrences.append(Occurrence(source, link, resolution))
            if resolution.status == "resolved":
                for destination in resolution.matches:
                    if destination != source and destination in notes:
                        incoming.add(destination)
    occurrences.sort(
        key=lambda item: (
            path_key(item.source),
            item.link.line if item.link.line is not None else -1,
            item.link.target,
            item.link.type,
            item.link.raw,
        )
    )
    return AuditReport(
        vault=index.root.name,
        files_scanned=scanned,
        occurrences=tuple(occurrences),
        orphan_notes=tuple(note for note in index.notes if note not in incoming),
        errors=tuple(sorted(errors, key=lambda issue: (path_key(issue.source), issue.reason))),
        skipped_paths=index.skipped_links,
    )
