# SPDX-License-Identifier: AGPL-3.0-or-later
"""« Document plateforme v1 » (ADR-0023, ADR-0036): checked when a person saves it, its blocks'
origin worked out from the version it was edited from, and rendered to controlled HTML.

The renderer, not the editor, is the reference: the editor's extensions reproduce it, which the
concordance test checks. Only the elements below are ever produced; every text is escaped and
no HTML is ever taken from a document.
"""

from __future__ import annotations

import json
import re
from html import escape
from typing import Any

Node = dict[str, Any]

# Closed lists (ADR-0036 §3): a document never carries an arbitrary font, size or colour.
FONTS = {
    "arial": "Arial, Helvetica, sans-serif",
    "calibri": "Calibri, Carlito, sans-serif",
    "cambria": "Cambria, Caladea, serif",
    "georgia": "Georgia, serif",
    "times": "'Times New Roman', Times, serif",
    "verdana": "Verdana, Geneva, sans-serif",
    "courier": "'Courier New', Courier, monospace",
}
SIZES = (9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36)  # points
COLORS = (
    "#000000",
    "#595959",
    "#c00000",
    "#e36c09",
    "#9c6500",
    "#00843d",
    "#0070c0",
    "#1f3864",
    "#7030a0",
    "#ffffff",
)
HIGHLIGHTS = ("#fff59d", "#c8e6c9", "#b3e5fc", "#f8bbd0", "#ffe0b2", "#e0e0e0")

BLOCKS = {"heading", "paragraph", "bullet_list", "ordered_list", "citation", "encadre"}
BLOCKS.add("separateur")
MARKS = {"bold", "italic", "strike", "highlight", "text_style", "link", "source_ref"}
# Nesting of the marks in the HTML, innermost first; the editor declares them in this order,
# reversed (Tiptap nests the first declared outermost).
MARK_ORDER = ("bold", "italic", "strike", "highlight", "text_style", "link", "source_ref")
ORIGINS = ("ia", "ia_modifie", "humain")
BLOCK_ID = re.compile(r"^b[0-9a-z]{1,12}$")
SOURCE_ID = re.compile(r"^S[0-9]{1,4}$")
LINK = re.compile(r"^(https?://|mailto:)[^\s<>\"]+$", re.IGNORECASE)
MAX_BYTES = 1_000_000
MAX_DEPTH = 6

MENTION_IA = (
    "Cet article a été rédigé avec l’aide d’une intelligence artificielle, "
    "puis relu et validé par la rédaction."
)
SOURCES_TITLE = "Sources"


class DocumentError(ValueError):
    """A document that does not follow the format: the reasons, for the person who saved it."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def check(document: Any, source_ids: set[str]) -> list[str]:
    """The errors of a document sent by the editor; empty when it is valid. `source_ids` are the
    sources of the article: a reference or a quotation may cite them, and nothing else."""
    if len(json.dumps(document, ensure_ascii=False).encode()) > MAX_BYTES:
        return ["document: too large"]
    if not isinstance(document, dict) or document.get("type") != "doc":
        return ["document: a doc is required"]
    errors: list[str] = []
    attrs = document.get("attrs")
    if not isinstance(attrs, dict) or attrs.get("version_schema") != 1:
        errors.append("document.attrs: version_schema 1 is required")
    content = document.get("content")
    if not isinstance(content, list) or not content:
        return [*errors, "document.content: one block at least is required"]
    for n, block in enumerate(content):
        _check_block(block, f"content[{n}]", source_ids, errors)
    return errors[:20]


def _check_block(block: Any, where: str, source_ids: set[str], errors: list[str]) -> None:
    if not isinstance(block, dict) or block.get("type") not in BLOCKS:
        errors.append(f"{where}: unknown block")
        return
    kind = block["type"]
    attrs = block.get("attrs") or {}
    if not isinstance(attrs, dict):
        errors.append(f"{where}.attrs: an object is required")
        return
    if attrs.get("id") is not None and not (
        isinstance(attrs["id"], str) and BLOCK_ID.match(attrs["id"])
    ):
        errors.append(f"{where}.attrs.id: invalid")
    if kind == "heading":
        if attrs.get("level") not in (2, 3, 4):
            errors.append(f"{where}.attrs.level: 2, 3 or 4")
        _check_inline(block.get("content"), where, source_ids, errors)
    elif kind == "paragraph":
        _check_inline(block.get("content"), where, source_ids, errors)
    elif kind in ("bullet_list", "ordered_list"):
        _check_list(block, where, source_ids, errors, 1)
    elif kind in ("citation", "encadre"):
        if kind == "citation" and attrs.get("source") not in source_ids:
            errors.append(f"{where}.attrs.source: one of the sources of the article")
        _check_paragraphs(block.get("content"), where, source_ids, errors)
    elif kind == "separateur" and block.get("content"):
        errors.append(f"{where}: a separator has no content")


def _check_paragraphs(content: Any, where: str, source_ids: set[str], errors: list[str]) -> None:
    if not isinstance(content, list) or not content:
        errors.append(f"{where}.content: one paragraph at least is required")
        return
    for m, paragraph in enumerate(content):
        if not isinstance(paragraph, dict) or paragraph.get("type") != "paragraph":
            errors.append(f"{where}.content[{m}]: a paragraph is required")
        else:
            _check_inline(paragraph.get("content"), f"{where}.content[{m}]", source_ids, errors)


def _check_list(
    node: Node, where: str, source_ids: set[str], errors: list[str], depth: int
) -> None:
    if depth > MAX_DEPTH:
        errors.append(f"{where}: lists nested too deep")
        return
    items = node.get("content")
    if not isinstance(items, list) or not items:
        errors.append(f"{where}.content: one item at least is required")
        return
    for m, item in enumerate(items):
        at = f"{where}.content[{m}]"
        children = item.get("content") if isinstance(item, dict) else None
        if (
            not isinstance(item, dict)
            or item.get("type") != "list_item"
            or not isinstance(children, list)
            or not children
        ):
            errors.append(f"{at}: a list item with content is required")
            continue
        if not isinstance(children[0], dict) or children[0].get("type") != "paragraph":
            errors.append(f"{at}.content[0]: a list item starts with a paragraph")
        for k, child in enumerate(children):
            kind = child.get("type") if isinstance(child, dict) else None
            if kind == "paragraph":
                _check_inline(child.get("content"), f"{at}.content[{k}]", source_ids, errors)
            elif kind in ("bullet_list", "ordered_list"):
                _check_list(child, f"{at}.content[{k}]", source_ids, errors, depth + 1)
            else:
                errors.append(f"{at}.content[{k}]: a paragraph or a list is required")


def _check_inline(content: Any, where: str, source_ids: set[str], errors: list[str]) -> None:
    if content is None:
        return
    if not isinstance(content, list):
        errors.append(f"{where}.content: a list is required")
        return
    for k, node in enumerate(content):
        at = f"{where}.content[{k}]"
        if not isinstance(node, dict) or node.get("type") != "text":
            errors.append(f"{at}: only text is allowed here")
            continue
        if not isinstance(node.get("text"), str) or not node["text"]:
            errors.append(f"{at}.text: a non-empty string is required")
        marks = node.get("marks") or []
        if not isinstance(marks, list):
            errors.append(f"{at}.marks: a list is required")
            continue
        seen = set()
        for mark in marks:
            kind = mark.get("type") if isinstance(mark, dict) else None
            if kind not in MARKS or kind in seen:
                errors.append(f"{at}.marks: unknown or repeated mark")
                continue
            seen.add(kind)
            mark_attrs = mark.get("attrs") or {}
            if kind == "link" and not LINK.match(str(mark_attrs.get("href", ""))):
                errors.append(f"{at}: a link goes to http, https or mailto")
            elif kind == "source_ref" and mark_attrs.get("source") not in source_ids:
                errors.append(f"{at}: a reference cites a source of the article")
            elif kind == "highlight" and mark_attrs.get("color") not in HIGHLIGHTS:
                errors.append(f"{at}: highlight colour not in the palette")
            elif kind == "text_style" and not _style_ok(mark_attrs):
                errors.append(f"{at}: font, size or colour not in the lists")


def _style_ok(attrs: Node) -> bool:
    font, size, color = attrs.get("font"), attrs.get("size"), attrs.get("color")
    return (
        set(attrs) <= {"font", "size", "color"}
        and (font is None or font in FONTS)
        and (size is None or (type(size) is int and size in SIZES))
        and (color is None or color in COLORS)
        and not (font is None and size is None and color is None)
    )


def with_origins(document: Node, previous: Node, sources: list[Node]) -> Node:
    """The document as saved: the sources of the article (never those sent), every top-level
    block with an id and its origin. A block left as it was keeps its origin; a block of the
    model that was changed is « ia_modifie »; a new block is « humain »."""
    before = {
        block["attrs"]["id"]: block
        for block in previous.get("content", [])
        if isinstance(block.get("attrs"), dict) and block["attrs"].get("id")
    }
    taken: set[str] = set()
    counter = max((int(i[1:], 36) for i in before if BLOCK_ID.match(i)), default=0)
    blocks = []
    for block in document["content"]:
        attrs = dict(block.get("attrs") or {})
        old = before.get(attrs.get("id") or "")
        if old is not None and attrs["id"] not in taken:
            same = _body(block) == _body(old)
            was = old["attrs"].get("origine", "humain")
            attrs["origine"] = was if same else ("ia_modifie" if was != "humain" else "humain")
        else:
            # A new block, or a part of a split one (the editor copies the id when a block is
            # split in two): the rest of a model's text stays « ia_modifie ».
            was = old["attrs"].get("origine", "humain") if old is not None else "humain"
            attrs["origine"] = "ia_modifie" if was != "humain" else "humain"
            counter += 1
            attrs["id"] = "b" + _base36(counter)
            while attrs["id"] in before or attrs["id"] in taken:
                counter += 1
                attrs["id"] = "b" + _base36(counter)
        taken.add(attrs["id"])
        blocks.append({**block, "attrs": attrs})
    language = (document.get("attrs") or {}).get("langue") or previous["attrs"].get("langue")
    return {
        "type": "doc",
        "attrs": {"version_schema": 1, "langue": language, "sources": sources},
        "content": blocks,
    }


def _body(block: Node) -> str:
    return json.dumps(
        {k: v for k, v in block.items() if k != "attrs"}, sort_keys=True, ensure_ascii=False
    )


def _base36(number: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        number, rest = divmod(number, 36)
        out = digits[rest] + out
        if number == 0:
            return out


def ai_share(document: Node) -> float:
    """Share of the text of top-level blocks whose origin is « ia » or « ia_modifie » (D8)."""
    total = generated = 0
    for block in document["content"]:
        length = len(plain_text(block))
        total += length
        if block.get("attrs", {}).get("origine") in ("ia", "ia_modifie"):
            generated += length
    return generated / total if total else 0.0


def plain_text(node: Node) -> str:
    if node["type"] == "text":
        return str(node["text"])
    return "".join(plain_text(child) for child in node.get("content", []))


def render(
    document: Node, mention: str = MENTION_IA, extras: bool = True, publication: bool = False
) -> str:
    """The HTML of a document. `extras=False` gives the body only, what the editor renders too;
    `publication=True` leaves out font, size and colour, which a site's theme decides."""
    sources = {s["id"]: s for s in document["attrs"]["sources"]}
    parts = [_block(block, sources, publication) for block in document["content"]]
    if not extras:
        return "\n".join(parts)
    if ai_share(document) > 0:
        parts.append(f'<p class="otlet-mention-ia"><em>{escape(mention)}</em></p>')
    if sources:
        items = "".join(f"<li>{_source(s)}</li>" for s in document["attrs"]["sources"])
        parts.append(
            f'<h2 class="otlet-sources-title">{SOURCES_TITLE}</h2>'
            f'<ol class="otlet-sources">{items}</ol>'
        )
    return "\n".join(parts)


def _source(source: Node) -> str:
    details = ", ".join(escape(v) for v in (source.get("editeur"), source.get("date")) if v)
    title = escape(source["titre"])
    link = f'<a href="{escape(source["url"])}">{title}</a>' if source.get("url") else title
    return f"{link}, {details}" if details else link


def _paragraphs(block: Node, publication: bool) -> str:
    return "".join(f"<p>{_inline(p.get('content', []), publication)}</p>" for p in block["content"])


def _block(block: Node, sources: dict[str, Node], publication: bool) -> str:
    kind = block["type"]
    if kind == "heading":
        level = block["attrs"]["level"]
        return f"<h{level}>{_inline(block.get('content', []), publication)}</h{level}>"
    if kind == "paragraph":
        return f"<p>{_inline(block.get('content', []), publication)}</p>"
    if kind in ("bullet_list", "ordered_list"):
        return _list(block, publication)
    if kind == "citation":
        source = sources.get(block["attrs"]["source"], {"titre": "?"})
        title = escape(source["titre"])
        linked = f'<a href="{escape(source["url"])}">{title}</a>' if source.get("url") else title
        # The attribution follows the quotation, outside <blockquote>: an editor can render
        # it from the node alone, and a CMS that rewrites quotations keeps a plain paragraph.
        return (
            f'<div class="otlet-citation"><blockquote>{_paragraphs(block, publication)}'
            f'</blockquote><p class="otlet-citation-source">— {linked}</p></div>'
        )
    if kind == "encadre":
        return f'<aside class="otlet-encadre">{_paragraphs(block, publication)}</aside>'
    if kind == "separateur":
        return "<hr>"
    raise ValueError(f"unknown block type {kind!r}")


def _list(node: Node, publication: bool) -> str:
    tag = "ul" if node["type"] == "bullet_list" else "ol"
    items = []
    for item in node["content"]:
        inner = []
        for child in item["content"]:
            if child["type"] == "paragraph":
                inner.append(f"<p>{_inline(child.get('content', []), publication)}</p>")
            else:
                inner.append(_list(child, publication))
        items.append(f"<li>{''.join(inner)}</li>")
    return f"<{tag}>{''.join(items)}</{tag}>"


def style(attrs: Node) -> str:
    """The inline style of a « text_style » mark, its properties always in this order."""
    parts = []
    if attrs.get("font"):
        parts.append(f"font-family: {FONTS[attrs['font']]}")
    if attrs.get("size"):
        parts.append(f"font-size: {attrs['size']}pt")
    if attrs.get("color"):
        parts.append(f"color: {attrs['color']}")
    return "; ".join(parts)


def _inline(content: list[Node], publication: bool) -> str:
    out = []
    for node in content:
        text = escape(node["text"], quote=False)
        marks = {m["type"]: m.get("attrs") or {} for m in node.get("marks", [])}
        for kind in MARK_ORDER:
            if kind not in marks:
                continue
            attrs = marks[kind]
            if kind == "bold":
                text = f"<strong>{text}</strong>"
            elif kind == "italic":
                text = f"<em>{text}</em>"
            elif kind == "strike":
                text = f"<s>{text}</s>"
            elif kind == "highlight":
                text = f'<mark style="background-color: {attrs["color"]}">{text}</mark>'
            elif kind == "text_style" and not publication:
                text = f'<span style="{escape(style(attrs))}">{text}</span>'
            elif kind == "link":
                text = f'<a href="{escape(attrs["href"])}">{text}</a>'
            elif kind == "source_ref":
                source = escape(attrs["source"])
                text = f'<span class="otlet-source-ref" data-source="{source}">{text}</span>'
        out.append(text)
    return "".join(out)
