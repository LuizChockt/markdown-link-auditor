"""Command-line interface and explicit, exclusive report output."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .auditor import audit_vault
from .reporter import json_report, text_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="markdown-auditor",
        description="Audit Markdown links without changing your notes or using the network.",
        epilog="Exit codes: 0 = complete audit; 1 = incomplete audit; 2 = usage/output error. "
        "Findings alone do not cause a nonzero exit code.",
    )
    parser.add_argument("path", metavar="PATH", type=Path, help="Markdown vault directory")
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="report format"
    )
    parser.add_argument(
        "--output", metavar="PATH", type=Path, help="new report file outside the vault"
    )
    parser.add_argument(
        "--exclude",
        metavar="PATTERN",
        action="append",
        default=[],
        help="vault-relative POSIX glob to exclude (repeatable; quote the pattern)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _validate_output(output: Path, root: Path, requested_root: Path) -> Path:
    absolute = Path(os.path.abspath(output.expanduser()))
    resolved = absolute.resolve()
    # Check both the user-facing tree and its physical location (including parent links).
    if absolute.is_relative_to(requested_root) or resolved.is_relative_to(root):
        raise ValueError("Report output must be outside the audited directory.")
    if absolute.exists() or absolute.is_symlink():
        raise ValueError("Report output already exists; existing files are never overwritten.")
    if not absolute.parent.is_dir():
        raise ValueError("Report output parent directory must already exist.")
    return absolute


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        requested_root = Path(os.path.abspath(args.path.expanduser()))
        root = requested_root.resolve()
        if not root.is_dir():
            raise ValueError("Vault path must be an existing directory.")
        output = (
            _validate_output(args.output, root, requested_root)
            if args.output is not None
            else None
        )
        report = audit_vault(root, tuple(args.exclude))
        rendered = json_report(report) if args.format == "json" else text_report(report)
        if output is not None:
            # Recheck after auditing; exclusive creation also rejects symlinks and races
            # that replace the output file itself. No existing file is ever truncated.
            output = _validate_output(output, root, requested_root)
            with output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
        else:
            sys.stdout.write(rendered)
        return 1 if report.errors else 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"{parser.prog}: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
