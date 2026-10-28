import json
import subprocess
import sys

import pytest

from markdown_auditor import __version__
from markdown_auditor.cli import main


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_help_and_version_work_without_path(option, capsys):
    with pytest.raises(SystemExit) as error:
        main([option])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "markdown-auditor" in output
    if option == "--version":
        assert __version__ in output


def test_default_text_report(make_vault, capsys):
    root = make_vault({"Home.md": "[[Missing]]"})
    assert main([str(root)]) == 0
    assert "MARKDOWN LINK AUDITOR" in capsys.readouterr().out


def test_json_stdout(make_vault, capsys):
    root = make_vault({"Home.md": "[[Missing]]"})
    assert main([str(root), "--format", "json"]) == 0
    captured = capsys.readouterr()
    assert not captured.err
    assert json.loads(captured.out)["summary"]["broken_links"] == 1


def test_repeatable_exclusions(make_vault, capsys):
    root = make_vault(
        {"Home.md": "", "Archive/Old.md": "[[Missing]]", ".obsidian/Note.md": "[[Bad]]"}
    )
    assert (
        main(
            [
                str(root),
                "--exclude",
                "Archive/**",
                "--exclude",
                ".obsidian/**",
                "--format",
                "json",
            ]
        )
        == 0
    )
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["files_scanned"] == 1
    assert data["summary"]["broken_links"] == 0


def test_output_creates_only_explicit_external_report(tmp_path, make_vault, capsys):
    root = make_vault({"Home.md": "[[Missing]]"})
    report = tmp_path / "audit.json"
    assert main([str(root), "--format", "json", "--output", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["summary"]["broken_links"] == 1
    assert list(root.iterdir()) == [root / "Home.md"]
    assert not capsys.readouterr().out


@pytest.mark.parametrize("existing_content", ["do not overwrite", ""])
def test_output_never_overwrites(tmp_path, make_vault, capsys, existing_content):
    root = make_vault({"Home.md": ""})
    output = tmp_path / "existing.md"
    output.write_text(existing_content, encoding="utf-8")
    assert main([str(root), "--output", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == existing_content
    assert "never overwritten" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["report.json", "Archive/report.json", "Home.md"])
def test_output_inside_vault_is_rejected_even_when_excluded(make_vault, capsys, name):
    root = make_vault({"Home.md": "untouched", "Archive/Old.md": ""})
    assert main([str(root), "--output", str(root / name), "--exclude", "Archive/**"]) == 2
    assert "outside the audited directory" in capsys.readouterr().err
    assert (root / "Home.md").read_text(encoding="utf-8") == "untouched"
    if name != "Home.md":
        assert not (root / name).exists()


def test_output_parent_link_into_vault_is_rejected(tmp_path, make_vault, make_symlink, capsys):
    root = make_vault({"Home.md": ""})
    alias = tmp_path / "alias"
    make_symlink(alias, root)
    assert main([str(root), "--output", str(alias / "report.json")]) == 2
    assert not (root / "report.json").exists()
    assert "outside the audited directory" in capsys.readouterr().err


def test_existing_or_dangling_output_symlink_is_rejected(tmp_path, make_vault, make_symlink):
    root = make_vault({"Home.md": ""})
    target = tmp_path / "not-created.md"
    link = tmp_path / "report.json"
    make_symlink(link, target)
    assert main([str(root), "--output", str(link)]) == 2
    assert not target.exists()


def test_file_created_during_audit_is_not_overwritten(tmp_path, make_vault, monkeypatch):
    import markdown_auditor.cli as module

    root = make_vault({"Home.md": ""})
    output = tmp_path / "report.json"
    original = module.audit_vault

    def competing_writer(*args, **kwargs):
        output.write_text("created by somebody else", encoding="utf-8")
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "audit_vault", competing_writer)
    assert main([str(root), "--output", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "created by somebody else"


def test_missing_output_parent_is_not_created(tmp_path, make_vault, capsys):
    root = make_vault({"Home.md": ""})
    output = tmp_path / "new-dir" / "report.json"
    assert main([str(root), "--output", str(output)]) == 2
    assert not output.parent.exists()
    assert "parent directory must already exist" in capsys.readouterr().err


def test_missing_vault_returns_clear_error(tmp_path, capsys):
    assert main([str(tmp_path / "missing")]) == 2
    assert "existing directory" in capsys.readouterr().err


def test_read_error_sets_exit_one_and_retains_valid_json(make_vault, capsys):
    root = make_vault({"Bad.md": b"\xff", "Good.md": "[[Missing]]"})
    assert main([str(root), "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["read_errors"] == 1
    assert data["summary"]["broken_links"] == 1


@pytest.mark.parametrize("args", [[], [".", "--format", "xml"], [".", "--unknown"]])
def test_invalid_arguments_exit_two(args):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2


def test_python_module_entry_point_works_from_other_directory(tmp_path, make_vault):
    root = make_vault({"Home.md": "[[Missing]]"})
    result = subprocess.run(
        [sys.executable, "-m", "markdown_auditor", str(root), "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["summary"]["broken_links"] == 1


def test_no_network_calls_are_made(make_vault, monkeypatch):
    import socket

    def forbid(*args, **kwargs):
        raise AssertionError("No network access is allowed")

    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    root = make_vault({"Home.md": "[site](https://example.org) [ftp](ftp://example.org)"})
    assert main([str(root)]) == 0
