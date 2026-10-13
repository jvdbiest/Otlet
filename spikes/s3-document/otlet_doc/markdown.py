# SPDX-License-Identifier: AGPL-3.0-or-later
"""S3.3: restricted Markdown of the AI outputs -> Document plateforme v1, deterministic.

The models are asked for this subset only (TECH_CHOICES.md §10.3); anything else is plain text:

    <!-- sources: [{"id": "S1", "titre": "…", "editeur": "…", "date": "2026-10-01", "url": "…"}] -->
    ## Intertitre            (### and #### too)
    Paragraphe, sur une ou plusieurs lignes.
    - puce                   (two spaces of indentation per nesting level)
    1. élément numéroté
    > Citation. {cite:S1}    (consecutive > lines; {cite:Sn} names its source, mandatory)
    ---                      (separator)
    Inline: **gras**, *italique*, [texte](https://…), [[passage annoté]]{src:S1}

Every block produced has origine "ia" and a sequential id.
"""

from __future__ import annotations

import json
import re
from typing import Any

Node = dict[str, Any]

SOURCES = re.compile(r"^<!--\s*sources:\s*(\[.*\])\s*-->\s*$", re.S)
HEADING = re.compile(r"^(#{2,4})\s+(.*)$")
LIST_ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
CITE = re.compile(r"\s*\{cite:(S\d+)\}\s*")
INLINE = re.compile(
    r"\[\[(?P<ref>.+?)\]\]\{src:(?P<src>S\d+)\}"
    r"|\[(?P<ltext>[^\]]+)\]\((?P<href>[^)\s]+)\)"
    r"|\*\*(?P<bold>.+?)\*\*"
    r"|\*(?P<italic>[^*]+?)\*"
)


class _Ids:
    def __init__(self) -> None:
        self.next = 0

    def __call__(self) -> str:
        self.next += 1
        return f"b{self.next}"


def inline(text: str, marks: list[Node] | None = None) -> list[Node]:
    marks = marks or []
    out: list[Node] = []
    position = 0
    for match in INLINE.finditer(text):
        if match.start() > position:
            out.append(_text(text[position : match.start()], marks))
        if match["ref"] is not None:
            out += inline(match["ref"], [*marks, {"type": "source_ref", "attrs": {"source": match["src"]}}])
        elif match["ltext"] is not None:
            out += inline(match["ltext"], [*marks, {"type": "link", "attrs": {"href": match["href"]}}])
        elif match["bold"] is not None:
            out += inline(match["bold"], [*marks, {"type": "bold"}])
        else:
            out += inline(match["italic"], [*marks, {"type": "italic"}])
        position = match.end()
    if position < len(text):
        out.append(_text(text[position:], marks))
    return [node for node in out if node["text"]]


def _text(text: str, marks: list[Node]) -> Node:
    node: Node = {"type": "text", "text": text}
    if marks:
        node["marks"] = sorted(marks, key=lambda m: ["link", "bold", "italic", "source_ref"].index(m["type"]))
    return node


def paragraph(text: str, attrs: Node | None = None) -> Node:
    node: Node = {"type": "paragraph"}
    if attrs is not None:
        node["attrs"] = attrs
    content = inline(text)
    if content:
        node["content"] = content
    return node


def _list(lines: list[tuple[int, str, str]], start: int, indent: int) -> tuple[Node, int]:
    kind = "ordered_list" if lines[start][1][0].isdigit() else "bullet_list"
    node: Node = {"type": kind, "content": []}
    index = start
    while index < len(lines) and lines[index][0] == indent:
        _, _, text = lines[index]
        item: Node = {"type": "list_item", "content": [paragraph(text)]}
        index += 1
        if index < len(lines) and lines[index][0] > indent:
            child, index = _list(lines, index, lines[index][0])
            item["content"].append(child)
        node["content"].append(item)
    return node, index


def convert(markdown: str, langue: str = "fr") -> Node:
    lines = markdown.replace("\r\n", "\n").split("\n")
    sources: list[Node] = []
    if lines and (match := SOURCES.match(lines[0])):
        sources = json.loads(match.group(1))
        lines = lines[1:]
    ids = _Ids()
    blocks: list[Node] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.strip() == "---":
            blocks.append({"type": "separateur", "attrs": {"id": ids(), "origine": "ia"}})
            index += 1
        elif heading := HEADING.match(line):
            blocks.append(
                {
                    "type": "heading",
                    "attrs": {"id": ids(), "origine": "ia", "level": len(heading.group(1))},
                    "content": inline(heading.group(2).strip()),
                }
            )
            index += 1
        elif line.startswith(">"):
            quoted = []
            while index < len(lines) and lines[index].startswith(">"):
                quoted.append(lines[index][1:].strip())
                index += 1
            text = " ".join(quoted)
            cite = CITE.search(text)
            if cite is None:
                raise ValueError("citation without {cite:Sn}")
            blocks.append(
                {
                    "type": "citation",
                    "attrs": {"id": ids(), "origine": "ia", "source": cite.group(1)},
                    "content": [paragraph(CITE.sub(" ", text).strip())],
                }
            )
        elif LIST_ITEM.match(line):
            items = []
            while index < len(lines) and (item := LIST_ITEM.match(lines[index])):
                items.append((len(item.group(1)), item.group(2), item.group(3).strip()))
                index += 1
            node, _ = _list(items, 0, items[0][0])
            node["attrs"] = {"id": ids(), "origine": "ia"}
            blocks.append({"type": node["type"], "attrs": node.pop("attrs"), "content": node["content"]})
        else:
            text = []
            while (
                index < len(lines)
                and lines[index].strip()
                and not HEADING.match(lines[index])
                and not lines[index].startswith(">")
                and not LIST_ITEM.match(lines[index])
                and lines[index].strip() != "---"
            ):
                text.append(lines[index].strip())
                index += 1
            blocks.append(paragraph(" ".join(text), {"id": ids(), "origine": "ia"}))
    return {
        "type": "doc",
        "attrs": {"version_schema": 1, "langue": langue, "sources": sources},
        "content": blocks,
    }
