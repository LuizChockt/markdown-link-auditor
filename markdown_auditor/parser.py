"""Extract links from CommonMark tokens, with a small Obsidian inline rule."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.rules_inline import autolink, image, link
from markdown_it.rules_inline.state_inline import StateInline

WIKILINK = re.compile(r"(!?)\[\[([^\[\]\n]+)\]\]")


@dataclass(frozen=True)
class Link:
    target: str
    type: str
    line: int | None
    raw: str
    embedded: bool = False


def _wikilink(state: StateInline, silent: bool) -> bool:
    match = WIKILINK.match(state.src, state.pos, state.posMax)
    if match is None:
        return False
    if not silent:
        token = state.push("wikilink", "", 0)
        token.content = match.group(2).split("|", 1)[0].strip()
        token.meta = {
            "offset": state.pos,
            "raw": match.group(0),
            "embedded": bool(match.group(1)),
        }
    state.pos = match.end()
    return True


InlineRule = Callable[[StateInline, bool], bool]


def _with_position(rule: InlineRule, token_type: str) -> InlineRule:
    """Record the opening position while the parser still knows its exact offset."""

    def wrapped(state: StateInline, silent: bool) -> bool:
        offset, first_token = state.pos, len(state.tokens)
        matched = rule(state, silent)
        if matched and not silent:
            for token in state.tokens[first_token:]:
                if token.type == token_type and "offset" not in token.meta:
                    token.meta.update(offset=offset, raw=state.src[offset : state.pos])
                    break
        return matched

    return wrapped


def _make_parser() -> MarkdownIt:
    parser = MarkdownIt("commonmark")
    # We only parse: accepting all URL schemes here never executes their content.
    parser.validateLink = lambda _url: True
    parser.inline.ruler.before("link", "wikilink", _wikilink)
    parser.inline.ruler.at("link", _with_position(link, "link_open"))
    parser.inline.ruler.at("image", _with_position(image, "image"))
    parser.inline.ruler.at("autolink", _with_position(autolink, "link_open"))
    return parser


def parse_links(text: str) -> list[Link]:
    """Return actual link uses; code, HTML blocks and unused definitions are ignored."""
    parsed: list[Link] = []
    for block in _make_parser().parse(text):
        if block.type != "inline":
            continue
        for token in block.children or []:
            if token.type not in {"wikilink", "link_open", "image"}:
                continue
            offset = token.meta.get("offset")
            line = None
            if block.map is not None and offset is not None:
                line = block.map[0] + block.content[:offset].count("\n") + 1
            if token.type == "wikilink":
                target, kind = token.content, "wikilink"
            else:
                target = token.attrGet("src" if token.type == "image" else "href") or ""
                kind = "markdown"
            parsed.append(
                Link(
                    target=target,
                    type=kind,
                    line=line,
                    raw=token.meta.get("raw", ""),
                    embedded=token.type == "image" or token.meta.get("embedded", False),
                )
            )
    return sorted(parsed, key=lambda item: item.line if item.line is not None else -1)
