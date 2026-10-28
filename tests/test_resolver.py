from pathlib import Path

import pytest

from markdown_auditor.parser import Link
from markdown_auditor.resolver import resolve_link
from markdown_auditor.scanner import scan_vault


def resolve(root, target, kind="wikilink", source="Home.md", embedded=False, excludes=()):
    return resolve_link(
        Link(target, kind, 1, "", embedded), Path(source), scan_vault(root, excludes)
    )


@pytest.mark.parametrize(
    ("target", "kind", "source", "expected"),
    [
        ("Python", "wikilink", "Home.md", "Python.md"),
        ("python.MD", "wikilink", "Home.md", "Python.md"),
        ("Notes/Data Structures", "wikilink", "Home.md", "Notes/Data Structures.md"),
        ("Data Structures", "wikilink", "Home.md", "Notes/Data Structures.md"),
        ("/Notes/Data Structures", "wikilink", "Home.md", "Notes/Data Structures.md"),
        ("../Python", "wikilink", "Notes/Home.md", "Python.md"),
        ("./Data Structures", "wikilink", "Notes/Home.md", "Notes/Data Structures.md"),
        ("Python#Functions", "wikilink", "Home.md", "Python.md"),
        ("Python^block", "wikilink", "Home.md", "Python.md"),
        ("Python#^block", "wikilink", "Home.md", "Python.md"),
        ("Notes/Data%20Structures.md", "markdown", "Home.md", "Notes/Data Structures.md"),
        ("../Python.md", "markdown", "Notes/Home.md", "Python.md"),
        ("./Python.md#heading", "markdown", "Home.md", "Python.md"),
        ("Python.md?download=1#heading", "markdown", "Home.md", "Python.md"),
        ("cafe\u0301", "wikilink", "Home.md", "Café.md"),
        ("CAF%C3%89.md", "markdown", "Home.md", "Café.md"),
        ("hash%23name.md", "markdown", "Home.md", "hash#name.md"),
        ("#Section", "wikilink", "Home.md", "Home.md"),
        ("^block", "wikilink", "Home.md", "Home.md"),
        ("#Section", "markdown", "Home.md", "Home.md"),
        ("", "markdown", "Home.md", "Home.md"),
        ("assets/image.png", "wikilink", "Home.md", "assets/image.png"),
        ("image.png", "wikilink", "Home.md", "assets/image.png"),
        ("assets/image.png", "markdown", "Home.md", "assets/image.png"),
        ("Notes/", "markdown", "Home.md", "Notes"),
    ],
)
def test_existing_targets(make_vault, target, kind, source, expected):
    root = make_vault(
        {
            "Home.md": "",
            "Notes/Home.md": "",
            "Python.md": "",
            "Notes/Data Structures.md": "",
            "Café.md": "",
            "hash#name.md": "",
            "assets/image.png": b"not opened",
        }
    )
    result = resolve(root, target, kind, source)
    assert result.status == "resolved"
    assert result.matches == (Path(expected),)


@pytest.mark.parametrize(
    ("target", "embedded", "reason"),
    [
        ("Missing", False, "target_not_found"),
        ("assets/missing.png", True, "attachment_not_found"),
        ("missing.png", True, "attachment_not_found"),
    ],
)
def test_missing_targets(make_vault, target, embedded, reason):
    result = resolve(make_vault({"Home.md": ""}), target, embedded=embedded)
    assert result.status == "broken"
    assert result.reason == reason


def test_duplicate_names_are_ambiguous_but_paths_are_unique(make_vault):
    root = make_vault({"Home.md": "", "Python/Intro.md": "", "JavaScript/Intro.md": ""})
    result = resolve(root, "Intro")
    assert result.status == "ambiguous"
    assert result.matches == (Path("JavaScript/Intro.md"), Path("Python/Intro.md"))
    assert resolve(root, "Python/Intro").matches == (Path("Python/Intro.md"),)


def test_markdown_does_not_search_other_directories_or_infer_extension(make_vault):
    root = make_vault({"Home.md": "", "Notes/Python.md": ""})
    assert resolve(root, "Python.md", "markdown").status == "broken"
    assert resolve(root, "Notes/Python", "markdown").status == "broken"


@pytest.mark.parametrize(
    "target",
    [
        "https://example.org",
        "http://example.org",
        "mailto:hello@example.org",
        "obsidian://open",
        "file:///private/Secret.md",
        "data:image/png;base64,AA==",
        "ftp://example.org",
        "//example.org/path",
    ],
)
def test_external_schemes_are_not_checked(make_vault, target):
    result = resolve(make_vault({"Home.md": ""}), target, "markdown")
    assert (result.status, result.reason) == ("external", "not_checked")


@pytest.mark.parametrize(
    "target",
    [
        "../Private.md",
        "../../Private.md",
        "/private/Secret.md",
        "C:/Private/Note.md",
        "C:\\Private\\Note.md",
        "\\\\server\\share\\Note.md",
        "%2e%2e/Private.md",
        "%2Fprivate/Note.md",
        "%43%3A/Private.md",
    ],
)
def test_out_of_scope_paths(make_vault, target):
    result = resolve(make_vault({"Home.md": ""}), target, "markdown")
    assert result.status == "out_of_scope"
    assert result.matches == ()


def test_escape_from_nested_note_and_return_is_checked_lexically(make_vault):
    root = make_vault({"Home.md": "", "Notes/Home.md": ""})
    assert (
        resolve(root, "../../vault/Home.md", "markdown", "Notes/Home.md").status
        == "out_of_scope"
    )


def test_explicit_exclusions_are_not_broken(make_vault):
    root = make_vault({"Home.md": "", "Archive/Old.md": ""})
    result = resolve(root, "Archive/Old", excludes=("Archive/**",))
    assert (result.status, result.reason) == ("ignored", "excluded_target")


def test_symlink_destinations_are_out_of_scope(tmp_path, make_vault, make_symlink):
    root = make_vault({"Home.md": ""})
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Private.md").write_text("private", encoding="utf-8")
    make_symlink(root / "linked", outside)
    make_symlink(root / "Alias.md", outside / "Private.md")
    assert resolve(root, "linked/Private").status == "out_of_scope"
    assert resolve(root, "Alias").status == "out_of_scope"


@pytest.mark.parametrize("names", [("A.md", "a.md"), ("Café.md", "Cafe\u0301.md")])
def test_case_and_unicode_collisions_are_never_chosen_arbitrarily(make_vault, names):
    root = make_vault({name: "" for name in names})
    if len(list(root.iterdir())) != 2:
        pytest.skip("Filesystem cannot store this spelling collision.")
    result = resolve(root, names[0], "markdown")
    assert result.status == "ambiguous"
    assert len(result.matches) == 2


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("folder%5CNote.md", "backslash_path"),
        ("Note%00.md", "invalid_target"),
        ("", "empty_wikilink"),
    ],
)
def test_unsupported_targets_are_not_broken(make_vault, target, reason):
    result = resolve(make_vault({"Home.md": ""}), target)
    assert (result.status, result.reason) == ("unsupported", reason)


def test_resolution_never_stats_or_opens_destination(make_vault, monkeypatch):
    root = make_vault({"Home.md": "", "Target.md": ""})
    index = scan_vault(root)

    def forbid(*args, **kwargs):
        raise AssertionError("Resolution must only use the index")

    for method in ("stat", "lstat", "resolve", "open"):
        monkeypatch.setattr(Path, method, forbid)
    assert (
        resolve_link(Link("../outside.md", "markdown", 1, ""), Path("Home.md"), index).status
        == "out_of_scope"
    )
    assert (
        resolve_link(Link("Target", "wikilink", 1, ""), Path("Home.md"), index).status
        == "resolved"
    )


@pytest.mark.parametrize("target", ["/", "./", "Notes/", "../"])
def test_directory_wikilinks_do_not_crash_or_become_broken(make_vault, target):
    root = make_vault({"Home.md": "", "Notes/Other.md": ""})
    result = resolve(root, target, source="Notes/Other.md")
    assert (result.status, result.reason) == ("unsupported", "directory_wikilink")


def test_directory_with_same_name_does_not_make_note_ambiguous(make_vault):
    root = make_vault({"Home.md": "", "Notes/Topic.md": "", "Notes/Topic/Nested.md": ""})
    result = resolve(root, "Notes/Topic")
    assert result.status == "resolved"
    assert result.matches == (Path("Notes/Topic.md"),)
