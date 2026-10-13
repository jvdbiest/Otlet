# SPDX-License-Identifier: AGPL-3.0-or-later
"""S3: extract the mandatory elements of docs/spikes/S3.md §2 from any HTML.

Used on our own rendering (to write expected.json) and on what WordPress and Ghost send back.
It relies on content, not on our CSS classes, which a CMS may strip:
- Sources block: the first list after a heading whose text is "Sources";
- AI mention: a paragraph whose text is the mention;
- citations: <blockquote>; the last link inside is the citation's source;
- headings: h1 to h6 except the Sources heading;
- links: every other <a href>.
Texts are normalized: entities decoded, whitespace folded, non-breaking spaces as spaces.
"""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any

from otlet_doc.render import MENTION_IA, SOURCES_TITLE

SPACES = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    return SPACES.sub(" ", unescape(text).replace(" ", " ").replace(" ", " ")).strip()


class _Tree(HTMLParser):
    """A minimal element tree: enough for headings, lists, blockquotes, links, paragraphs."""

    VOID = {"br", "img", "hr", "meta", "link", "input", "source", "col", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: dict[str, Any] = {"tag": "root", "attrs": {}, "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1]["children"].append(data)


def parse(html: str) -> dict[str, Any]:
    tree = _Tree()
    tree.feed(html)
    tree.close()
    return tree.root


def text_of(node: Any) -> str:
    if isinstance(node, str):
        return node
    return "".join(text_of(child) for child in node["children"])


def walk(node: Any) -> Any:
    if isinstance(node, str):
        return
    yield node
    for child in node["children"]:
        yield from walk(child)


def extract(html: str) -> dict[str, Any]:
    root = parse(html)
    elements = [n for n in walk(root) if n is not root]
    headings, links, citations, sources = [], [], [], []
    excluded: set[int] = set()
    mention = False

    # Sources block: first list after the "Sources" heading, in document order.
    seen_sources_heading = False
    for node in elements:
        if re.fullmatch(r"h[1-6]", node["tag"]) and normalize_text(text_of(node)) == SOURCES_TITLE:
            seen_sources_heading = True
            continue
        if seen_sources_heading and node["tag"] in ("ol", "ul"):
            for anchor in walk(node):
                if anchor["tag"] == "a" and anchor["attrs"].get("href"):
                    sources.append(
                        {"href": anchor["attrs"]["href"], "titre": normalize_text(text_of(anchor))}
                    )
                    excluded.add(id(anchor))
            break

    for node in elements:
        tag = node["tag"]
        if re.fullmatch(r"h[1-6]", tag):
            text = normalize_text(text_of(node))
            if text != SOURCES_TITLE:
                headings.append({"level": int(tag[1]), "text": text})
        elif tag == "p" and normalize_text(text_of(node)) == normalize_text(MENTION_IA):
            mention = True
        elif tag == "blockquote":
            anchors = [a for a in walk(node) if a["tag"] == "a" and a["attrs"].get("href")]
            source = anchors[-1]["attrs"]["href"] if anchors else None
            if anchors:
                excluded.add(id(anchors[-1]))
            paragraphs = [
                normalize_text(text_of(p))
                for p in node["children"]
                if not isinstance(p, str) and p["tag"] == "p"
            ]
            body = [p for p in paragraphs if not p.startswith("—")] or [normalize_text(text_of(node))]
            citations.append({"text": " ".join(body), "source": source})

    for node in elements:
        if node["tag"] == "a" and node["attrs"].get("href") and id(node) not in excluded:
            links.append({"href": node["attrs"]["href"], "text": normalize_text(text_of(node))})

    return {
        "headings": headings,
        "links": links,
        "citations": citations,
        "sources": sources,
        "mention_ia": mention,
    }
