import hashlib
import json
from pathlib import Path

from markdown_auditor.auditor import audit_vault
from markdown_auditor.reporter import json_report, text_report


def test_orphans_received_links_self_links_and_ambiguity(make_vault):
    root = make_vault(
        {
            "Home.md": "[[Target]] [[Intro]] [[Home]]",
            "Target.md": "",
            "Self.md": "[[Self]]",
            "Standalone.md": "",
            "A/Intro.md": "",
            "B/Intro.md": "",
        }
    )
    report = audit_vault(root)
    assert report.orphan_notes == (
        Path("A/Intro.md"),
        Path("B/Intro.md"),
        Path("Home.md"),
        Path("Self.md"),
        Path("Standalone.md"),
    )
    assert report.summary["resolved_links"] == 3
    assert report.summary["ambiguous_links"] == 1


def test_note_embeds_are_confirmed_incoming_links(make_vault):
    report = audit_vault(make_vault({"Home.md": "![[Target]]", "Target.md": ""}))
    assert report.orphan_notes == (Path("Home.md"),)


def test_terminal_report_escapes_control_characters(make_vault):
    root = make_vault({"Home.md": "[[Bad\x1bName]]"})
    rendered = text_report(audit_vault(root))
    assert "\x1b" not in rendered
    assert r"[[Bad\x1bName]]" in rendered


def test_all_summary_categories_are_counted_separately(make_vault):
    root = make_vault(
        {
            "Home.md": (
                "[[Target]] [[Missing]] [[Intro]] [site](https://example.org)\n"
                "[outside](../Private.md) [[Archive/Old]] [unsupported](<dir\\Note.md>)"
            ),
            "Target.md": "",
            "A/Intro.md": "",
            "B/Intro.md": "",
            "Archive/Old.md": "",
        }
    )
    report = audit_vault(root, ("Archive/**",))
    assert report.summary == {
        "files_scanned": 4,
        "internal_links": 6,
        "resolved_links": 1,
        "broken_links": 1,
        "ambiguous_links": 1,
        "orphan_notes": 3,
        "external_links": 1,
        "out_of_scope_links": 1,
        "ignored_links": 1,
        "unsupported_links": 1,
        "read_errors": 0,
    }
    assert (
        sum(
            report.summary[key]
            for key in (
                "resolved_links",
                "broken_links",
                "ambiguous_links",
                "out_of_scope_links",
                "ignored_links",
                "unsupported_links",
            )
        )
        == report.summary["internal_links"]
    )


def test_ordering_is_stable_by_path_line_then_target(make_vault):
    root = make_vault({"z.md": "[[Z]]\n[[A]]", "a.md": "\n[[Y]] [[B]]"})
    report = audit_vault(root)
    assert [
        (item.source.as_posix(), item.link.line, item.link.target)
        for item in report.occurrences
    ] == [
        ("a.md", 2, "B"),
        ("a.md", 2, "Y"),
        ("z.md", 1, "Z"),
        ("z.md", 2, "A"),
    ]
    assert json_report(report) == json_report(audit_vault(root))


def test_audit_does_not_change_files_or_create_new_ones(make_vault):
    root = make_vault(
        {
            "Home.md": "---\ntitle: Synthetic\n---\n[[Missing]]\n![[assets/image.png]]",
            "Other.md": "[[Home]]",
            "assets/image.png": bytes(range(256)),
        }
    )

    def snapshot():
        return {
            path.relative_to(root).as_posix(): (
                hashlib.sha256(path.read_bytes()).hexdigest(),
                path.stat().st_mtime_ns,
            )
            for path in root.rglob("*")
            if path.is_file()
        }

    before = snapshot()
    first = json_report(audit_vault(root))
    second = json_report(audit_vault(root))
    assert first == second
    assert snapshot() == before


def test_attachments_are_never_read(make_vault, monkeypatch):
    root = make_vault({"Home.md": "![[assets/image.png]]", "assets/image.png": b"binary"})
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path.suffix.casefold() == ".md", "Attachments must not be opened"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    assert audit_vault(root).summary["resolved_links"] == 1


def test_invalid_encoding_is_a_read_error_not_an_empty_note(make_vault):
    root = make_vault({"Home.md": "[[Unreadable]]", "Unreadable.md": b"\xff\xfe\x00"})
    report = audit_vault(root)
    assert report.summary["files_scanned"] == 1
    assert report.summary["read_errors"] == 1
    assert report.errors[0].source == "Unreadable.md"
    assert report.summary["resolved_links"] == 1  # File exists; its content could not be read.
    assert "may be incomplete" in text_report(report)


def test_note_permission_failure_does_not_abort_other_notes(make_vault, monkeypatch):
    root = make_vault({"Allowed.md": "[[Missing]]", "Denied.md": "[[Secret]]"})
    original = Path.read_text

    def deny(path, *args, **kwargs):
        if path.name == "Denied.md":
            raise PermissionError("synthetic failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", deny)
    report = audit_vault(root)
    assert report.summary["broken_links"] == report.summary["files_scanned"] == 1
    assert report.errors[0].reason == "note_unreadable"


def test_utf8_bom_is_read_normally(make_vault):
    report = audit_vault(make_vault({"Home.md": b"\xef\xbb\xbf[[Target]]", "Target.md": ""}))
    assert report.summary["resolved_links"] == 1
    assert report.occurrences[0].link.line == 1


def test_json_schema_has_consistent_occurrences_and_no_absolute_paths(make_vault):
    root = make_vault({"Home.md": "[[Missing]] [[Intro]]", "A/Intro.md": "", "B/Intro.md": ""})
    rendered = json_report(audit_vault(root))
    data = json.loads(rendered)
    fields = {"source", "line", "target", "type", "reason", "matches"}
    assert set(data["broken_links"][0]) == set(data["ambiguous_links"][0]) == fields
    assert data["broken_links"][0] == {
        "source": "Home.md",
        "line": 1,
        "target": "Missing",
        "type": "wikilink",
        "reason": "target_not_found",
        "matches": [],
    }
    assert str(root) not in rendered
    assert data["vault"] == "vault"


def test_report_labels_potential_orphans_and_external_links(make_vault):
    report = audit_vault(make_vault({"Home.md": "[site](https://example.org)"}))
    rendered = text_report(report)
    assert "Potential orphan" in rendered
    assert "standalone note may be intentional" in rendered
    assert "External (not checked)" in rendered
    assert report.summary["resolved_links"] == report.summary["broken_links"] == 0


def test_text_report_includes_real_lines_and_possible_matches(make_vault):
    root = make_vault(
        {"Home.md": "\n[[Missing]]\n[[Intro]]", "A/Intro.md": "", "B/Intro.md": ""}
    )
    rendered = text_report(audit_vault(root))
    assert "Home.md:2\n  [[Missing]]\n  Target not found" in rendered
    assert "Home.md:3\n  [[Intro]]" in rendered
    assert "  - A/Intro.md\n  - B/Intro.md" in rendered


def test_reading_note_rechecks_symlink_created_after_scanning(
    tmp_path, make_vault, make_symlink, monkeypatch
):
    import markdown_auditor.auditor as module

    root = make_vault({"Home.md": "original"})
    outside = tmp_path / "outside.md"
    outside.write_text("[[Must not parse]]", encoding="utf-8")
    original = module.scan_vault

    def replace_after_scan(*args, **kwargs):
        index = original(*args, **kwargs)
        (root / "Home.md").unlink()
        make_symlink(root / "Home.md", outside)
        return index

    monkeypatch.setattr(module, "scan_vault", replace_after_scan)
    report = audit_vault(root)
    assert not report.occurrences
    assert report.errors[0].reason == "note_unreadable"


def test_external_symlink_content_is_never_opened(
    tmp_path, make_vault, make_symlink, monkeypatch
):
    root = make_vault({"Home.md": "[[linked/Private]]"})
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Private.md").write_text("[[Private content]]", encoding="utf-8")
    make_symlink(root / "linked", outside)
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path == root / "Home.md"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    report = audit_vault(root)
    assert report.summary["out_of_scope_links"] == 1
    assert report.skipped_paths == (Path("linked"),)
