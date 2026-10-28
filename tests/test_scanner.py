from pathlib import Path

import pytest

from markdown_auditor.scanner import matches_exclude, scan_vault


def test_empty_vault(tmp_path):
    index = scan_vault(tmp_path)
    assert index.notes == index.files == ()
    assert not index.errors


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_root(tmp_path, kind):
    path = tmp_path / "invalid"
    if kind == "file":
        path.write_text("not a directory", encoding="utf-8")
    with pytest.raises(ValueError, match="existing directory"):
        scan_vault(path)


def test_recursive_markdown_case_and_attachment_index(make_vault):
    root = make_vault({"Home.md": "", "a/Note.MD": "", "a/b/Third.mD": "", "image.png": b"x"})
    index = scan_vault(root)
    assert [p.as_posix() for p in index.notes] == ["a/b/Third.mD", "a/Note.MD", "Home.md"]
    assert len(index.files) == 4
    assert index.by_name["image.png"] == (Path("image.png"),)


def test_excluded_folders_are_pruned_without_traversal(make_vault, monkeypatch):
    root = make_vault({"Home.md": "", "Archive/Old.md": "", ".obsidian/config.json": "{}"})
    original = Path.iterdir

    def guarded(path):
        assert path.name not in {"Archive", ".obsidian"}
        return original(path)

    monkeypatch.setattr(Path, "iterdir", guarded)
    index = scan_vault(root, ("Archive/**", ".obsidian/**"))
    assert index.files == (Path("Home.md"),)


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("Archive", "Archive/**", True),
        ("Archive/2020/Old.md", "Archive/**", True),
        ("x/Archive/Old.md", "Archive/**", False),
        ("x/Archive/Old.md", "**/Archive/**", True),
        ("Note.md", "**/*.md", True),
        ("a/Note.MD", "*.md", True),
        ("a/note.txt", "*.md", False),
        ("Notes/a/keep.md", "Notes/*.md", False),
        ("Notes/a/keep.md", "Notes/**/keep.?d", True),
        ("a/cache/value.md", "cache", True),
        ("b/Note.md", "[ab]/*.md", True),
    ],
)
def test_portable_glob_semantics(path, pattern, expected):
    assert matches_exclude(Path(path), (pattern,)) is expected


def test_external_directory_symlink_is_never_traversed(tmp_path, make_vault, make_symlink):
    root = make_vault({"Home.md": ""})
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Private.md").write_text("[[Do not parse]]", encoding="utf-8")
    make_symlink(root / "linked", outside)
    index = scan_vault(root)
    assert index.notes == (Path("Home.md"),)
    assert index.skipped_links == (Path("linked"),)


def test_file_and_internal_symlinks_are_skipped(make_vault, make_symlink):
    root = make_vault({"Home.md": "", "Notes/Other.md": ""})
    make_symlink(root / "alias.md", root / "Home.md")
    make_symlink(root / "loop", root)
    index = scan_vault(root)
    assert len(index.notes) == 2
    assert index.skipped_links == (Path("alias.md"), Path("loop"))


def test_directory_read_error_is_reported(make_vault, monkeypatch):
    root = make_vault({"Home.md": "", "Restricted/Note.md": ""})
    original = Path.iterdir

    def deny(path):
        if path.name == "Restricted":
            raise PermissionError("synthetic permission failure")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", deny)
    index = scan_vault(root)
    assert index.notes == (Path("Home.md"),)
    assert [(e.source, e.reason) for e in index.errors] == [
        ("Restricted", "directory_unreadable")
    ]
    assert index.restriction(Path("Restricted/Note.md")) == ("ignored", "unreadable_scope")


def test_entry_metadata_error_is_reported(make_vault, monkeypatch):
    root = make_vault({"Missing.md": ""})
    original = Path.lstat

    def deny(path, *args, **kwargs):
        if path.name == "Missing.md":
            raise PermissionError("synthetic failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", deny)
    index = scan_vault(root)
    assert not index.notes
    assert index.errors[0].reason == "entry_unreadable"
