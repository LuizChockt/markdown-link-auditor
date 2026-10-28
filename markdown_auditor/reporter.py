"""Stable terminal and JSON reports, using vault-relative paths only."""

from __future__ import annotations

import json

from .auditor import AuditReport

REASONS = {
    "target_not_found": "Target not found",
    "attachment_not_found": "Attachment not found",
    "multiple_targets": "Multiple possible targets",
    "not_checked": "External link (not checked)",
    "absolute_path": "Absolute path is outside the audited scope",
    "outside_vault": "Path leaves the audited folder",
    "symlink_not_followed": "Symlink or reparse point is not followed",
    "excluded_target": "Target is excluded from this audit",
    "unreadable_scope": "Target could not be indexed",
    "backslash_path": "Use forward slashes in local links",
    "invalid_target": "Control characters in destination are not supported",
    "empty_wikilink": "Empty wikilinks are not supported",
    "directory_wikilink": "Wikilinks to directories are not supported",
}


def json_report(report: AuditReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"


def _safe(value: str) -> str:
    # Keep control characters in filenames/labels from becoming terminal instructions.
    return "".join(char if char.isprintable() else repr(char)[1:-1] for char in value)


def text_report(report: AuditReport) -> str:
    summary = report.summary
    lines = [
        "MARKDOWN LINK AUDITOR",
        "=====================",
        "",
        f"Vault: {_safe(report.vault)}/",
        "",
    ]
    for label, key in (
        ("Files scanned", "files_scanned"),
        ("Internal links", "internal_links"),
        ("Resolved links", "resolved_links"),
        ("Broken links", "broken_links"),
        ("Ambiguous links", "ambiguous_links"),
        ("Orphan notes", "orphan_notes"),
        ("External (not checked)", "external_links"),
        ("Out of scope", "out_of_scope_links"),
        ("Ignored links", "ignored_links"),
        ("Unsupported links", "unsupported_links"),
        ("Read errors", "read_errors"),
    ):
        lines.append(f"{label + ':':<25}{summary[key]:>6}")

    def section(title: str) -> None:
        lines.extend(
            [
                "",
                "---------------------------------",
                title,
                "---------------------------------",
                "",
            ]
        )

    for status, title in (
        ("broken", "BROKEN LINKS"),
        ("ambiguous", "AMBIGUOUS LINKS"),
        ("out_of_scope", "OUT OF SCOPE"),
        ("ignored", "IGNORED LINKS"),
        ("unsupported", "UNSUPPORTED LINKS"),
    ):
        items = [item for item in report.occurrences if item.resolution.status == status]
        if not items and status not in {"broken", "ambiguous"}:
            continue
        section(title)
        if not items:
            lines.append("None.")
        for item in items:
            location = item.source.as_posix()
            if item.link.line is not None:
                location += f":{item.link.line}"
            reason = item.resolution.reason or ""
            lines.extend(
                [
                    _safe(location),
                    "  " + _safe(item.link.raw or item.link.target),
                    "  " + REASONS.get(reason, reason),
                ]
            )
            if item.resolution.matches:
                lines.append("  Possible matches:")
                lines.extend(
                    "  - " + _safe(path.as_posix()) for path in item.resolution.matches
                )
            lines.append("")

    section("ORPHAN NOTES")
    lines.extend("- " + _safe(path.as_posix()) for path in report.orphan_notes)
    if not report.orphan_notes:
        lines.append("None.")
    lines.extend(
        [
            "",
            "Potential orphan = no confirmed link from another scanned Markdown note.",
            "A standalone note may be intentional. Ambiguous and self-links do not count.",
        ]
    )
    if report.errors:
        section("READ ERRORS")
        lines.extend(f"- {_safe(error.source)}: {error.reason}" for error in report.errors)
        lines.append(
            "Backlink and orphan results may be incomplete because some content was unreadable."
        )
    if report.skipped_paths:
        section("SKIPPED SYMLINKS / REPARSE POINTS")
        lines.extend("- " + _safe(path.as_posix()) for path in report.skipped_paths)
    section("SUMMARY")
    lines.extend(
        [
            f"{summary['broken_links']} broken links",
            f"{summary['ambiguous_links']} ambiguous links",
            f"{summary['orphan_notes']} potential orphan notes",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
