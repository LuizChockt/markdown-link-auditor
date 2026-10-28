"""Discover files without following symlinks or opening attachments."""

from __future__ import annotations

import stat
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import cache
from pathlib import Path, PurePosixPath


def normalized(value: str) -> str:
    """Use the same Unicode and case comparison on every operating system."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", value).casefold())


def path_key(path: Path | str) -> tuple[str, str]:
    value = path.as_posix() if isinstance(path, Path) else path
    return normalized(value), value


def _glob_matches(parts: tuple[str, ...], pattern: tuple[str, ...]) -> bool:
    @cache
    def match(i: int, j: int) -> bool:
        if j == len(pattern):
            # A matching directory also excludes all of its descendants.
            return True
        if pattern[j] == "**":
            return match(i, j + 1) or (i < len(parts) and match(i + 1, j))
        return i < len(parts) and fnmatchcase(parts[i], pattern[j]) and match(i + 1, j + 1)

    return match(0, 0)


def matches_exclude(path: Path, patterns: tuple[str, ...]) -> bool:
    """Match root-relative POSIX globs; a bare pattern matches any component."""
    parts = tuple(normalized(part) for part in path.parts)
    for pattern in patterns:
        pattern = normalized(pattern.strip("/"))
        if not pattern:
            continue
        if "/" not in pattern:
            if any(fnmatchcase(part, pattern) for part in parts):
                return True
        elif _glob_matches(parts, PurePosixPath(pattern).parts):
            return True
    return False


def is_link(path: Path) -> bool:
    """Also reject Windows junctions/reparse points, including on Python 3.11."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


@dataclass(frozen=True)
class FileIssue:
    source: str
    reason: str


@dataclass
class VaultIndex:
    root: Path
    files: tuple[Path, ...]
    notes: tuple[Path, ...]
    directories: frozenset[Path]
    by_path: dict[str, tuple[Path, ...]]
    by_name: dict[str, tuple[Path, ...]]
    excludes: tuple[str, ...]
    skipped_links: tuple[Path, ...]
    unreadable_paths: tuple[Path, ...]
    errors: tuple[FileIssue, ...]

    def restriction(self, path: Path) -> tuple[str, str] | None:
        key = normalized(path.as_posix())
        for skipped in self.skipped_links:
            prefix = normalized(skipped.as_posix())
            if key == prefix or key.startswith(prefix + "/"):
                return "out_of_scope", "symlink_not_followed"
        if matches_exclude(path, self.excludes):
            return "ignored", "excluded_target"
        for unreadable in self.unreadable_paths:
            prefix = normalized(unreadable.as_posix())
            if key == prefix or key.startswith(prefix + "/"):
                return "ignored", "unreadable_scope"
        return None


def scan_vault(root: Path, excludes: tuple[str, ...] = ()) -> VaultIndex:
    """Index regular files and directories, reporting recoverable scan errors."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Vault path must be an existing directory.")

    files: list[Path] = []
    directories = [Path(".")]
    skipped: list[Path] = []
    unreadable: list[Path] = []
    errors: list[FileIssue] = []

    def visit(directory: Path) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda p: path_key(p.name))
        except OSError:
            relative = directory.relative_to(root)
            unreadable.append(relative)
            errors.append(FileIssue(relative.as_posix(), "directory_unreadable"))
            return
        for entry in entries:
            relative = entry.relative_to(root)
            if matches_exclude(relative, excludes):
                continue
            try:
                if is_link(entry):
                    skipped.append(relative)
                elif entry.is_dir():
                    directories.append(relative)
                    visit(entry)
                elif entry.is_file():
                    files.append(relative)
                # Sockets, devices and pipes are never opened or indexed.
            except OSError:
                unreadable.append(relative)
                errors.append(FileIssue(relative.as_posix(), "entry_unreadable"))

    visit(root)
    files.sort(key=path_key)
    notes = tuple(path for path in files if path.suffix.casefold() == ".md")
    by_path: dict[str, list[Path]] = defaultdict(list)
    by_name: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(files + directories, key=path_key):
        by_path[normalized(path.as_posix())].append(path)
    for path in files:
        by_name[normalized(path.name)].append(path)
    return VaultIndex(
        root=root,
        files=tuple(files),
        notes=notes,
        directories=frozenset(directories),
        by_path={key: tuple(value) for key, value in by_path.items()},
        by_name={key: tuple(value) for key, value in by_name.items()},
        excludes=excludes,
        skipped_links=tuple(sorted(skipped, key=path_key)),
        unreadable_paths=tuple(sorted(unreadable, key=path_key)),
        errors=tuple(sorted(errors, key=lambda issue: path_key(issue.source))),
    )
