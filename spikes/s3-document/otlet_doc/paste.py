# SPDX-License-Identifier: AGPL-3.0-or-later
"""S3.3: HTML pasted from Word or Google Docs -> Document plateforme v1.

Keeps only what the format knows: headings, paragraphs, lists (nested), bold, italic, links,
and quotations. A quotation is a paragraph styled as a quote (Word: class MsoQuote; Google
Docs: left margin of 30 pt or more) followed by an attribution paragraph starting with "—"
whose link is one of the document's sources. Everything else (styles, classes, spans, Word's
conditional comments and list bullets) is dropped. Every block gets origine "humain".
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from otlet_doc.markdown import _Ids, _text

Node = dict[str, Any]

MARGIN = re.compile(r"margin-left:\s*([\d.]+)\s*pt")
MSO_LIST = re.compile(r"mso-list:\s*\w+\s+level(\d+)")


class _Collector(HTMLParser):
    """Turns the pasted HTML into a flat list of raw blocks with their inline runs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Node] = []
        self.current: Node | None = None
        self.marks: list[tuple[str, Node]] = []  # (tag, mark) stack
        self.skip = 0  # inside <style>, <script>, <title> or Word's supportLists bullet
        self.list_marker = ""
        self.gdocs_lists: list[str] = []  # stack of "ul"/"ol"

    # Word wraps list bullets in <![if !supportLists]> … <![endif]>.
    def unknown_decl(self, data: str) -> None:
        if data.strip().startswith("if !supportLists"):
            self.skip += 1
        elif data.strip().startswith("endif") and self.skip:
            self.skip -= 1

    def handle_comment(self, data: str) -> None:
        pass

    def _open_block(self, kind: str, **attrs: Any) -> None:
        self.current = {"kind": kind, "runs": [], **attrs}
        self.blocks.append(self.current)

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: v or "" for k, v in attrs_list}
        style = attrs.get("style", "").replace(" ", "").lower()
        if tag in ("style", "script", "title", "head"):
            self.skip += 1
            return
        if tag in ("ul", "ol"):
            self.gdocs_lists.append(tag)
            return
        if re.fullmatch(r"h[1-6]", tag):
            self._open_block("heading", level=min(max(int(tag[1]), 2), 4))
        elif tag == "li":
            level = int(attrs.get("aria-level") or len(self.gdocs_lists) or 1)
            self._open_block("item", ordered=self.gdocs_lists[-1:] == ["ol"], level=level)
        elif tag == "p":
            klass = attrs.get("class", "")
            mso = MSO_LIST.search(style)
            margin = MARGIN.search(style)
            if mso and "MsoListParagraph" in klass:
                self._open_block("item", ordered=None, level=int(mso.group(1)))
            elif "MsoQuote" in klass or "IntenseQuote" in klass or (margin and float(margin.group(1)) >= 30):
                self._open_block("quote")
            elif self.current is not None and self.current["kind"] == "item" and self.current.get("open"):
                pass  # Google Docs: <li><p>…</p></li>
            else:
                self._open_block("paragraph")
        mark: Node | None = None
        if tag in ("b", "strong") and "font-weight:normal" not in style:
            mark = {"type": "bold"}
        elif tag in ("i", "em"):
            mark = {"type": "italic"}
        elif tag == "span" and ("font-weight:700" in style or "font-weight:bold" in style):
            mark = {"type": "bold"}
        elif tag == "span" and "font-style:italic" in style:
            mark = {"type": "italic"}
        elif tag == "a" and attrs.get("href", "").startswith(("http://", "https://", "mailto:")):
            mark = {"type": "link", "attrs": {"href": attrs["href"]}}
        if mark is not None:
            self.marks.append((tag, mark))
        elif tag in ("b", "strong", "i", "em", "span", "a"):
            self.marks.append((tag, {}))
        if tag == "li" and self.current is not None:
            self.current["open"] = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script", "title", "head"):
            self.skip = max(0, self.skip - 1)
            return
        if tag in ("ul", "ol") and self.gdocs_lists:
            self.gdocs_lists.pop()
            return
        if tag in ("b", "strong", "i", "em", "span", "a"):
            for index in range(len(self.marks) - 1, -1, -1):
                if self.marks[index][0] == tag:
                    del self.marks[index]
                    break
        if tag == "li" and self.current is not None:
            self.current["open"] = False

    def handle_data(self, data: str) -> None:
        if self.skip:
            if self.current is not None and self.current["kind"] == "item":
                marker = data.strip()
                if marker and self.current.get("ordered") is None:
                    self.current["ordered"] = bool(re.match(r"^\d+[.)]?$", marker))
            return
        text = re.sub(r"\s+", " ", data.replace(" ", " "))
        if not text.strip() and (self.current is None or not self.current["runs"]):
            return
        if self.current is None:
            self._open_block("paragraph")
        assert self.current is not None
        marks = [m for _, m in self.marks if m]
        self.current["runs"].append((text, marks))


def _inline(runs: list[tuple[str, list[Node]]]) -> list[Node]:
    out: list[Node] = []
    for text, marks in runs:
        node = _text(text, [dict(m) for m in marks])
        if out and out[-1].get("marks") == node.get("marks"):
            out[-1]["text"] += node["text"]
        else:
            out.append(node)
    # Trim the edges of the block.
    if out:
        out[0]["text"] = out[0]["text"].lstrip()
        out[-1]["text"] = out[-1]["text"].rstrip()
    return [node for node in out if node["text"]]


def _plain(runs: list[tuple[str, list[Node]]]) -> str:
    return "".join(text for text, _ in runs).strip()


def convert(html: str, sources: list[Node], langue: str = "fr") -> Node:
    collector = _Collector()
    collector.feed(html)
    collector.close()
    raw = [b for b in collector.blocks if _plain(b["runs"])]
    by_url = {s["url"]: s["id"] for s in sources}
    ids = _Ids()
    attrs = lambda: {"id": ids(), "origine": "humain"}  # noqa: E731
    blocks: list[Node] = []
    index = 0
    while index < len(raw):
        block = raw[index]
        kind = block["kind"]
        if kind == "heading":
            blocks.append({"type": "heading", "attrs": {**attrs(), "level": block["level"]}, "content": _inline(block["runs"])})
            index += 1
        elif kind == "quote":
            quoted = [block]
            index += 1
            while index < len(raw) and raw[index]["kind"] == "quote" and not _plain(raw[index]["runs"]).startswith("—"):
                quoted.append(raw[index])
                index += 1
            attribution = raw[index] if index < len(raw) and _plain(raw[index]["runs"]).startswith("—") else None
            source = None
            if attribution is not None:
                hrefs = [m["attrs"]["href"] for _, marks in attribution["runs"] for m in marks if m["type"] == "link"]
                source = next((by_url[h] for h in hrefs if h in by_url), None)
            if source is None:
                for q in quoted:  # not a recognized quotation: keep the text as paragraphs
                    blocks.append({"type": "paragraph", "attrs": attrs(), "content": _inline(q["runs"])})
                continue
            index += 1
            blocks.append(
                {
                    "type": "citation",
                    "attrs": {**attrs(), "source": source},
                    "content": [{"type": "paragraph", "content": _inline(q["runs"])} for q in quoted],
                }
            )
        elif kind == "item":
            items = []
            while index < len(raw) and raw[index]["kind"] == "item":
                items.append(raw[index])
                index += 1
            blocks.append(_list(items, attrs()))
        else:
            blocks.append({"type": "paragraph", "attrs": attrs(), "content": _inline(block["runs"])})
            index += 1
    return {"type": "doc", "attrs": {"version_schema": 1, "langue": langue, "sources": sources}, "content": blocks}


def _list(items: list[Node], attrs: Node) -> Node:
    def build(start: int, level: int) -> tuple[Node, int]:
        ordered = bool(items[start].get("ordered"))
        node: Node = {"type": "ordered_list" if ordered else "bullet_list", "content": []}
        index = start
        while index < len(items) and items[index]["level"] >= level:
            if items[index]["level"] > level:
                child, index = build(index, items[index]["level"])
                node["content"][-1]["content"].append(child)
                continue
            node["content"].append(
                {"type": "list_item", "content": [{"type": "paragraph", "content": _inline(items[index]["runs"])}]}
            )
            index += 1
        return node, index

    node, _ = build(0, items[0]["level"])
    return {"type": node["type"], "attrs": attrs, "content": node["content"]}
