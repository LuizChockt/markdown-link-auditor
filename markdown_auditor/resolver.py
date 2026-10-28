"""Resolve references exclusively against the in-scope file index."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from .parser import Link
from .scanner import VaultIndex, normalized, path_key

SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True)
class Resolution:
    status: str
    reason: str | None = None
    matches: tuple[Path, ...] = ()


def _collapse(path: str, base: Path) -> Path | None:
    parts = list(base.parts) if base != Path(".") else []
    for part in path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return Path(*parts) if parts else Path(".")


def _result(matches: set[Path], missing_reason: str) -> Resolution:
    ordered = tuple(sorted(matches, key=path_key))
    if len(ordered) == 1:
        return Resolution("resolved", matches=ordered)
    if ordered:
        return Resolution("ambiguous", "multiple_targets", ordered)
    return Resolution("broken", missing_reason)


def resolve_link(link: Link, source: Path, index: VaultIndex) -> Resolution:
    """No guessed destination is opened, stat'ed or resolved on the filesystem."""
    raw = link.target
    # Windows drive paths must not become URI schemes, even on Unix.
    decoded = unquote(raw)
    if WINDOWS_DRIVE.match(raw) or WINDOWS_DRIVE.match(decoded) or decoded.startswith("\\"):
        return Resolution("out_of_scope", "absolute_path")
    if SCHEME.match(raw) or raw.startswith("//"):
        return Resolution("external", "not_checked")

    path = raw.split("#", 1)[0]
    if link.type == "wikilink":
        path = path.split("^", 1)[0].strip()
    else:
        path = path.split("?", 1)[0]
    path = unquote(path)
    if any(ord(char) < 32 for char in path):
        return Resolution("unsupported", "invalid_target")
    if "\\" in path:
        return Resolution("unsupported", "backslash_path")
    if path.startswith("/") and link.type != "wikilink":
        return Resolution("out_of_scope", "absolute_path")

    if not path:
        # An empty destination or fragment-only reference points to the current note.
        if link.type == "wikilink" and not raw.startswith(("#", "^")):
            return Resolution("unsupported", "empty_wikilink")
        return Resolution("resolved", matches=(source,))

    missing_reason = "attachment_not_found" if link.embedded else "target_not_found"
    if link.type == "wikilink" and "/" not in path:
        names = [path] if path.casefold().endswith(".md") else [path, path + ".md"]
        matches = {match for name in names for match in index.by_name.get(normalized(name), ())}
        # A skipped link may be a basename target, but its destination is never inspected.
        if not matches and any(
            normalized(skipped.name) in {normalized(name) for name in names}
            for skipped in index.skipped_links
        ):
            return Resolution("out_of_scope", "symlink_not_followed")
        return _result(matches, missing_reason)

    if link.type == "wikilink":
        base = source.parent if path.startswith(("./", "../")) else Path(".")
        path = path.lstrip("/")
    else:
        base = source.parent
    destination = _collapse(path, base)
    if destination is None:
        return Resolution("out_of_scope", "outside_vault")
    if link.type == "wikilink" and destination == Path("."):
        return Resolution("unsupported", "directory_wikilink")
    candidates = [destination]
    if link.type == "wikilink" and destination.suffix.casefold() != ".md":
        candidates.append(destination.with_name(destination.name + ".md"))

    matches: set[Path] = set()
    directory_match = False
    restrictions: list[tuple[str, str]] = []
    for candidate in candidates:
        restriction = index.restriction(candidate)
        if restriction is not None:
            restrictions.append(restriction)
        else:
            for match in index.by_path.get(normalized(candidate.as_posix()), ()):
                if link.type == "wikilink" and match in index.directories:
                    directory_match = True
                else:
                    matches.add(match)
    if not matches and restrictions:
        return Resolution(*restrictions[0])
    if not matches and directory_match:
        return Resolution("unsupported", "directory_wikilink")
    return _result(matches, missing_reason)
