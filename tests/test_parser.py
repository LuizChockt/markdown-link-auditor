import pytest

from markdown_auditor.parser import parse_links


@pytest.mark.parametrize(
    ("text", "target", "kind", "embedded"),
    [
        ("[[Python]]", "Python", "wikilink", False),
        ("[[Python|Programming language]]", "Python", "wikilink", False),
        ("[[Python#Functions]]", "Python#Functions", "wikilink", False),
        ("[[Python^block-id]]", "Python^block-id", "wikilink", False),
        ("![[assets/diagram.png]]", "assets/diagram.png", "wikilink", True),
        ("[Python](Python.md)", "Python.md", "markdown", False),
        ("[Guide](../Guides/Guide.md)", "../Guides/Guide.md", "markdown", False),
        ("![Picture](assets/image.png)", "assets/image.png", "markdown", True),
        ("[Space](<Data Structures.md>)", "Data%20Structures.md", "markdown", False),
        ('[Title](Note.md "A title")', "Note.md", "markdown", False),
        ("[Parentheses](Note_(draft).md)", "Note_(draft).md", "markdown", False),
        ("[Site](https://example.org)", "https://example.org", "markdown", False),
        ("<https://example.org>", "https://example.org", "markdown", False),
        ("[Email](mailto:hello@example.org)", "mailto:hello@example.org", "markdown", False),
        (
            "[Custom](obsidian://open?vault=demo)",
            "obsidian://open?vault=demo",
            "markdown",
            False,
        ),
        ("[Local](file:///private/note.md)", "file:///private/note.md", "markdown", False),
    ],
)
def test_supported_syntax(text, target, kind, embedded):
    links = parse_links(text)
    assert len(links) == 1
    assert (links[0].target, links[0].type, links[0].embedded) == (target, kind, embedded)
    assert links[0].line == 1
    assert links[0].raw == text


@pytest.mark.parametrize(
    "text",
    [
        "```markdown\n[[False]]\n[False](Missing.md)\n```",
        "~~~\n![[False.png]]\n~~~",
        "    [[False]]\n    [False](Missing.md)",
        "Use `[[Example]]` and `[False](Missing.md)` here.",
        "Use ``a ` [[Example]] b`` here.",
        "<!-- [[False]] [False](Missing.md) -->",
        "<div>\n[[False]]\n</div>",
        r"\[\[Escaped\]\] and \[example](Missing.md)",
        "[unused]: Missing.md",
        "[Not a valid link](unquoted spaces.md)",
    ],
)
def test_non_links_and_code_are_ignored(text):
    assert parse_links(text) == []


def test_reference_style_uses_are_parsed_at_usage_lines():
    links = parse_links("[First][ref]\n\n[ref]: Note.md\n\n[ref]\n")
    assert [(link.target, link.line) for link in links] == [("Note.md", 1), ("Note.md", 5)]


def test_exact_lines_inside_containers_and_repeated_targets():
    text = (
        "# Heading\n\n"
        "> [[One]]\n> [Two](Two.md)\n\n"
        "- [[Three]]\n  continuation [Four](Four.md)\n\n"
        "[[One]] [One](One.md)\n"
    )
    assert [(link.target, link.line) for link in parse_links(text)] == [
        ("One", 3),
        ("Two.md", 4),
        ("Three", 6),
        ("Four.md", 7),
        ("One", 9),
        ("One.md", 9),
    ]


def test_multiline_label_uses_opening_line():
    links = parse_links("Text\n[long\nlabel](Note.md)\n")
    assert links[0].line == 2
    assert links[0].target == "Note.md"


def test_image_inside_link_is_counted_but_image_alt_links_are_not():
    links = parse_links("[![alt](pic.png)](Note.md) ![a [[not a reference]]](other.png)")
    assert [link.target for link in links] == ["Note.md", "pic.png", "other.png"]


def test_code_does_not_hide_real_link_on_same_line():
    links = parse_links("`[[Example]]` then ![[Real.png]] and [[Real]]")
    assert [link.target for link in links] == ["Real.png", "Real"]


def test_crlf_and_bom():
    links = parse_links("# Heading\r\n\r\n[[Target]]\r\n")
    assert links[0].line == 3


def test_wikilinks_take_precedence_over_reference_label_definitions():
    links = parse_links("[[Note]]\n\n[Note]: Different.md\n")
    assert len(links) == 1
    assert (links[0].target, links[0].type) == ("Note", "wikilink")
