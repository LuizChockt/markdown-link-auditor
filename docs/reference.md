> [Project overview](../README.md) · [Português](../README.pt-BR.md)

# Markdown Link Auditor

*A lightweight Python CLI that scans Markdown knowledge bases for broken links, missing attachments, ambiguous references, and orphan notes.*

## Project overview

Notes are easy to rename and move; their backlinks are easy to miss. This tool
checks a folder of Markdown notes against a local file index and reports broken
links, ambiguous destinations, and notes with no confirmed incoming links.

Version **0.1.0** is a small, read-only CLI. It never repairs notes or contacts
websites. Python **3.11 or newer** is required. Its only runtime dependency is
[`markdown-it-py`](https://github.com/executablebooks/markdown-it-py).

## Features

- Recursive discovery of `.md` files, including `.MD` and mixed-case extensions.
- Obsidian wikilinks and embeds, including aliases and file-level heading/block references.
- CommonMark inline links, images, autolinks, and uses of reference-style links.
- Missing note and attachment detection; duplicate names reported as ambiguous.
- Potential orphan notes, excluding self-links and unconfirmed ambiguous links.
- Text and JSON reports with stable ordering and source line numbers.
- Repeatable glob exclusions, with no traversal of excluded directories.
- Separate reporting for external, out-of-scope, ignored, and unsupported destinations.
- Unicode NFC normalization and case-insensitive matching on every platform.

## Supported Markdown links

| Syntax | Behavior |
| --- | --- |
| `[[Python]]` | Search the audited index for `Python.md` or an exact filename. |
| `[[Notes/Python]]` | Resolve the explicit vault-relative path. |
| `[[Python\|Programming language]]` | Ignore the alias when resolving. |
| `[[Python#Functions]]` / `[[Python#^block-id]]` | Validate the file only. |
| `[[#Functions]]` / `[[^block-id]]` | Refer to the current note. |
| `![[diagram.png]]` / `![[assets/diagram.png]]` | Check attachment existence without opening it. |
| `[Python](../Python.md)` | Resolve relative to the source note's directory. |
| `[Guide](../../Guides/Guide.md)` | Support relative paths within the audited folder. |
| `[Data](../Notes/Data%20Structures.md)` | Percent-decode the path. |
| `[Data](../<Notes/Data Structures.md>)` | Support spaces with CommonMark angle brackets. |
| `![Diagram](../assets/diagram.svg)` | Check the image destination. |
| `[Python][ref]` with `[ref]: Python.md` | Audit each use, at its usage line. |
| `[Website](https://example.org)` / `<https://example.org>` | Count as external and leave unchecked. |
| `[Email](../mailto:hello@example.org)` | Count as external and leave unchecked. |

Links inside fenced code, indented code, and inline code are ignored. HTML blocks
and comments are not treated as Markdown link content. Unused link definitions
are not counted as link uses. Bare website addresses are not automatically linkified.

### Resolution rules

1. **Wikilinks with paths:** `Notes/Python` and `/Notes/Python` start at the vault
   root. Explicit `./` and `../` paths start at the source note's directory.
   There is no additional basename fallback for a failed explicit path.
2. **Wikilinks without paths:** search all non-excluded indexed files by basename.
   Unless the target already ends in `.md`, consider both the exact filename and
   the filename plus `.md`. A single match resolves; multiple matches are ambiguous.
   Even a same-directory match does not override a duplicate elsewhere.
3. **Markdown links:** resolve only the stated path relative to the source file.
   Do not infer `.md` or search other folders. Existing indexed directories are
   accepted, but do not contribute backlinks to notes.
4. **Fragments:** remove literal `#fragment` before decoding the path. For
   wikilinks, also remove `^block`. Markdown query strings are ignored.
   `%23` can therefore refer to a literal `#` in a filename.
5. **Portable matching:** compare paths using Unicode NFC plus `casefold()`.
   All matching candidates are retained, including collisions in explicit paths.
   Matching is deliberately case-insensitive even on Linux. Reported paths retain
   their actual spelling, use `/`, and are sorted by normalized path and line.
6. **Scope:** collapse `.` and `..` lexically. A path that escapes the root is
   out of scope, even if later components would return inside. Absolute Markdown
   paths and Windows drive/UNC paths are also out of scope. Symlinks and Windows
   reparse points, including junctions, are skipped entirely, even if internal.
   The resolver uses the index and never probes a guessed external destination.

Use `/` in links on every platform. Backslash-separated local paths are reported
as unsupported; rooted Windows paths are reported as out of scope. Any URI scheme
(`http:`, `https:`, `mailto:`, `file:`, `obsidian:`, and others), plus protocol-relative
URLs such as `//example.org/path`, is external and never opened.

## Obsidian compatibility

The supported subset covers ordinary note references, path-qualified links,
aliases, note embeds, and attachment embeds. `![[Python]]` contributes a confirmed
incoming link to `Python.md`, just like `[[Python]]`.

This is not an implementation of Obsidian's full resolution engine. It does not
read Obsidian settings or apply nearest-note heuristics. Duplicated basenames are
always reported as ambiguous unless a path makes the destination unique.

## Installation

Download and extract the source, then open a terminal in the project directory:

```bash
cd markdown-link-auditor
python -m venv .venv
```

Activate the environment:

```bash
# Linux / macOS
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install from the local source:

```bash
python -m pip install -e ".[dev]"
```

The `dev` extra adds pytest. For runtime use only, use `python -m pip install .`
instead. No PyPI release is required or assumed.

## CLI usage

```bash
python -m markdown_auditor --help
python -m markdown_auditor --version
python -m markdown_auditor "examples/sample-vault"
python -m markdown_auditor "examples/sample-vault" --format json
```

The installed `markdown-auditor` command offers the same interface:

```bash
markdown-auditor "examples/sample-vault"
```

For another folder on Windows:

```powershell
python -m markdown_auditor "D:\Markdown\MyVault"
```

| Argument | Description |
| --- | --- |
| `PATH` | Folder to audit recursively. |
| `--format text` | Human-readable report; the default. |
| `--format json` | Structured JSON report. |
| `--output PATH` | Create a new UTF-8 report outside the audited tree. |
| `--exclude PATTERN` | Exclude a vault-relative glob; repeat as needed. |
| `--version` | Print the version and exit. |

Explicitly save a report in the project directory, outside the sample vault:

```bash
python -m markdown_auditor "examples/sample-vault" --format json --output "audit-report.json"
```

The output's parent directory must already exist. Existing files, including empty
files and symlinks, are rejected. An output path inside the vault is rejected even
if excluded. The report goes to the file only when `--output` is given; otherwise
it goes to standard output. Errors go to standard error.

| Exit code | Meaning |
| --- | --- |
| `0` | Complete audit, including audits that found problems. |
| `1` | Incomplete audit because a note or directory could not be read; report still produced. |
| `2` | Invalid arguments, invalid root, or an output/operating-system error. |

## Example output

All demonstration files are synthetic. The sample's `Home.md` contains:

```markdown
# My Knowledge Base

- [[Python]]
- [[JavaScript]]
- [[Missing Note]]
- [[Notes/Algorithms]]
- [Data Structures](../Notes/Data%20Structures.md)
- ![Diagram](../assets/diagram.svg)
- ![[assets/missing-image.png]]
- [[Introduction]]
- [Python website](https://www.python.org/)
```

This command:

```bash
python -m markdown_auditor examples/sample-vault
```

produces the following report, also available as
[`examples/reports/sample-report.txt`](../examples/reports/sample-report.txt):

```text
MARKDOWN LINK AUDITOR
=====================

Vault: sample-vault/

Files scanned:                8
Internal links:              10
Resolved links:               7
Broken links:                 2
Ambiguous links:              1
Orphan notes:                 4
External (not checked):       1
Out of scope:                 0
Ignored links:                0
Unsupported links:            0
Read errors:                  0

---------------------------------
BROKEN LINKS
---------------------------------

Home.md:5
  [[Missing Note]]
  Target not found

Home.md:9
  ![[assets/missing-image.png]]
  Attachment not found


---------------------------------
AMBIGUOUS LINKS
---------------------------------

Home.md:10
  [[Introduction]]
  Multiple possible targets
  Possible matches:
  - JavaScript/Introduction.md
  - Python/Introduction.md


---------------------------------
ORPHAN NOTES
---------------------------------

- Home.md
- JavaScript/Introduction.md
- Productivity.md
- Python/Introduction.md

Potential orphan = no confirmed link from another scanned Markdown note.
A standalone note may be intentional. Ambiguous and self-links do not count.

---------------------------------
SUMMARY
---------------------------------

2 broken links
1 ambiguous links
4 potential orphan notes
```

`Python.md` also has one self-link, and `Notes/Algorithms.md` links to `Python.md`.
These account for the two additional resolved links beyond those in `Home.md`.

An orphan classification means only that no other successfully parsed Markdown
note has a confirmed link to the file. Standalone notes can be intentional.
Ambiguous links and self-links do not count as incoming links. Unreadable or
excluded sources may make backlink results incomplete.

## JSON report

```bash
python -m markdown_auditor examples/sample-vault --format json
```

The exact sample JSON is checked in as
[`examples/reports/sample-report.json`](../examples/reports/sample-report.json):

```json
{
  "vault": "sample-vault",
  "summary": {
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
    "read_errors": 0
  },
  "broken_links": [
    {
      "source": "Home.md",
      "line": 5,
      "target": "Missing Note",
      "type": "wikilink",
      "reason": "target_not_found",
      "matches": []
    },
    {
      "source": "Home.md",
      "line": 9,
      "target": "assets/missing-image.png",
      "type": "wikilink",
      "reason": "attachment_not_found",
      "matches": []
    }
  ],
  "ambiguous_links": [
    {
      "source": "Home.md",
      "line": 10,
      "target": "Introduction",
      "type": "wikilink",
      "reason": "multiple_targets",
      "matches": [
        "JavaScript/Introduction.md",
        "Python/Introduction.md"
      ]
    }
  ],
  "external_links": [
    {
      "source": "Home.md",
      "line": 11,
      "target": "https://www.python.org/",
      "type": "markdown",
      "reason": "not_checked",
      "matches": []
    }
  ],
  "out_of_scope_links": [],
  "ignored_links": [],
  "unsupported_links": [],
  "orphan_notes": [
    "Home.md",
    "JavaScript/Introduction.md",
    "Productivity.md",
    "Python/Introduction.md"
  ],
  "errors": [],
  "skipped_paths": []
}
```

Each occurrence has the same fields: `source`, `line`, `target`, `type`, `reason`,
and `matches`. `line` is a one-based opening line or `null` if unavailable; `matches`
is an empty array unless candidate files exist. `type` is `wikilink` or `markdown`.
Targets preserve parsed destinations; conventional Markdown URLs may remain
percent-encoded in the report. Source and match paths are vault-relative.

Resolved links are counted in `summary` and omitted from the occurrence arrays to
keep reports focused. `internal_links` includes resolved, broken, ambiguous,
out-of-scope, ignored, and unsupported references, but excludes external URLs.
`files_scanned` counts Markdown files whose content was successfully read; it does
not count attachments. Read failures are listed in `errors`, and skipped symlinks
and reparse points in `skipped_paths`. No timestamps or absolute vault paths are
added, so an unchanged tree produces identical reports.

## Excluding folders

```bash
python -m markdown_auditor "examples/sample-vault" --exclude ".obsidian/**" --exclude "Archive/**"
python -m markdown_auditor "examples/sample-vault" --exclude "**/drafts/**" --exclude "*.tmp"
```

Quote globs so the shell does not expand them. Patterns use `/`, Unicode NFC,
and case-insensitive matching on all platforms:

- A pattern with `/` is anchored at the vault root.
- `*`, `?`, and `[abc]` operate within one path component; `**` spans zero or more.
- `Archive/**` excludes `Archive` itself and everything beneath it.
- A bare pattern such as `*.tmp` or `.git` matches any component, at any depth.
- Matching a directory prunes its entire subtree. There are no implicit exclusions
  or gitignore-style negation rules.

Path-qualified references into an excluded subtree are `ignored`, not broken.
Excluded folders are never traversed, so their contents cannot satisfy basename
wikilinks. A bare `[[Old]]` can therefore be reported missing if its only destination
is in an excluded folder. Exclusions deliberately define the knowledge available
to this audit.

## Project structure

```text
markdown-link-auditor/
├── markdown_auditor/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── scanner.py
│   ├── parser.py
│   ├── resolver.py
│   ├── auditor.py
│   └── reporter.py
├── tests/
│   ├── conftest.py
│   ├── test_scanner.py
│   ├── test_parser.py
│   ├── test_resolver.py
│   ├── test_auditor.py
│   ├── test_cli.py
│   └── test_examples.py
├── examples/
│   ├── sample-vault/
│   │   ├── Home.md
│   │   ├── Python.md
│   │   ├── JavaScript.md
│   │   ├── Productivity.md
│   │   ├── Notes/
│   │   │   ├── Algorithms.md
│   │   │   └── Data Structures.md
│   │   ├── Python/Introduction.md
│   │   ├── JavaScript/Introduction.md
│   │   └── assets/diagram.svg
│   └── reports/
│       ├── sample-report.txt
│       └── sample-report.json
├── .github/workflows/tests.yml
├── .gitattributes
├── .gitignore
├── LICENSE
├── MANIFEST.in
├── README.md
└── pyproject.toml
```

## Running tests

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Tests use temporary synthetic vaults and the checked-in sample. They exercise
parsing, resolution, duplicate names, Unicode/case behavior, scope boundaries,
exclusions, read errors, actual CLI execution, deterministic reporting, unchanged
file contents/mtimes, no new vault files, and safe output creation. The checked-in
text/JSON reports and their reference-guide examples are compared against actual output.

The GitHub Actions workflow runs pytest on pushes and pull requests, with Python
3.11 and 3.14 on Linux, Windows, and macOS. Creating symlinks and storing colliding
case/Unicode filenames depend on filesystem/account capabilities; the relevant
tests skip explicitly where those fixtures cannot be created. A configured matrix
does not imply it has already run on GitHub.

## Privacy and safety

- No network requests, telemetry, APIs, or content uploads during auditing.
- No writes, repairs, metadata edits, moves, renames, or deletions in the vault.
- Only Markdown note content is opened; attachments are checked through the index.
- Symlink and Windows reparse-point entries under the selected root are neither
  read nor traversed. An explicitly selected root is canonicalized before scanning.
- External, absolute, and escaping destinations are never checked for existence.
- Reports are written only with explicit `--output`, outside the audited tree,
  using exclusive creation so an existing file is never truncated.
- No configuration or cache files are generated in the vault by the auditor.
- All included notes, attachments, and test fixtures are fictional.

The scanner and output writer check filesystem boundaries again before access.
This is an ordinary local CLI, not a sandbox against concurrent hostile filesystem
changes. For reproducible audits, use a stable tree rather than changing files or
symlinked report-parent directories during a run. Operating systems may update
file access times as a normal consequence of reading.

## Current limitations

- Headings, anchors, and Obsidian block IDs are not validated, only their files.
- Wikilinks to explicit directory paths are reported as unsupported. Conventional
  Markdown directory links are supported.
- No HTTP checks, repairs, graph rendering, attachment-content inspection, or
  unused-attachment detection.
- Supported input encoding is UTF-8, optionally with a BOM. Other encodings and
  unreadable notes produce explicit read errors and exit code `1`.
- Unsupported Obsidian extensions, escaped delimiters in wikilinks, multiline
  wikilinks, raw HTML `href`/`src` attributes, and links generated by templates are
  not interpreted. Front matter has no special YAML semantics; Markdown-looking
  content there may be parsed as Markdown.
- Invalid CommonMark links, such as unquoted spaces in a destination, remain text
  and are not reported as broken links. Use `%20` or `<angle brackets>` for spaces.
- Every URI scheme is left unchecked, including `file:` and `obsidian:` URLs.
- Case-insensitive matching is intentional; a resolved case mismatch may still
  need correction for another tool or a case-sensitive web host.
- Excluded content and skipped symlinks do not contribute backlinks. Basename
  resolution searches only indexed files. Orphans are candidates for review.
- Filesystem-specific filenames/collisions cannot be reproduced on filesystems
  that cannot store them. The tool does not emulate those missing files.

## Roadmap

These are future possibilities, not implemented features.

### v0.2 — Enhanced link analysis

- Heading and anchor validation.
- Obsidian block-reference validation.
- Unused attachment detection.
- Suggested targets for broken links.

### v0.3 — Knowledge graph

- Note connection graph.
- Disconnected component detection.
- Backlink statistics.
- Interactive HTML visualization.

### v0.4 — Advanced reporting

- HTML reports.
- CSV export.
- Audit comparisons.
- Issue prioritization.

### v1.0 — Optional repair assistant

- Suggested corrections and change previews.
- Explicit confirmation before applying any repair.
- Backups and rollback support.

Version 0.1 remains strictly read-only.

## License

[MIT](../LICENSE).
