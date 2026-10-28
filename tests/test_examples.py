"""Keep the checked-in demonstration and README output reproducible."""

import json
from pathlib import Path

from markdown_auditor.auditor import audit_vault
from markdown_auditor.reporter import json_report, text_report

PROJECT = Path(__file__).resolve().parents[1]


def test_checked_in_sample_has_expected_findings():
    report = audit_vault(PROJECT / "examples/sample-vault")
    assert report.summary == {
        "files_scanned": 8,
        "internal_links": 10,
        "resolved_links": 7,
        "broken_links": 2,
        "ambiguous_links": 1,
        "orphan_notes": 4,
        "external_links": 1,
        "out_of_scope_links": 0,
        "ignored_links": 0,
        "unsupported_links": 0,
        "read_errors": 0,
    }


def test_checked_in_reports_and_readme_match_actual_output():
    report = audit_vault(PROJECT / "examples/sample-vault")
    readme = (PROJECT / "README.md").read_text(encoding="utf-8")
    text = text_report(report)
    structured = json_report(report)
    assert (PROJECT / "examples/reports/sample-report.txt").read_text(encoding="utf-8") == text
    assert (PROJECT / "examples/reports/sample-report.json").read_text(
        encoding="utf-8"
    ) == structured
    assert text.rstrip() in readme
    assert structured.rstrip() in readme
    assert json.loads(structured)["summary"]["files_scanned"] == 8
