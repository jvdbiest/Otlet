# SPDX-License-Identifier: AGPL-3.0-or-later
"""S3.3: Python renderer, Document plateforme v1 (JSON) -> controlled HTML.

The renderer, not the CMS connector, inserts the AI mention and the Sources block
(ARCHITECTURE.md §14.5). Only the elements below are ever produced: no HTML is copied
from the document, every text is escaped.
"""

from __future__ import annotations

from html import escape
from typing import Any

Node = dict[str, Any]

MENTION_IA = (
    "Cet article a été rédigé avec l’aide d’une intelligence artificielle, "
    "puis relu et validé par la rédaction."
)
SOURCES_TITLE = "Sources"


def ai_share(doc: Node) -> float:
    """Share of the text of top-level blocks whose origin is `ia` or `ia_modifie` (D8)."""
    total = generated = 0
    for block in doc["content"]:
        length = len(plain_text(block))
        total += length
        if block.get("attrs", {}).get("origine") in ("ia", "ia_modifie"):
            generated += length
    return generated / total if total else 0.0


def plain_text(node: Node) -> str:
    if node["type"] == "text":
        return str(node["text"])
    return "".join(plain_text(child) for child in node.get("content", []))


def render(doc: Node, mention: str = MENTION_IA) -> str:
    sources = {s["id"]: s for s in doc["attrs"]["sources"]}
    numbers = {source_id: index + 1 for index, source_id in enumerate(sources)}
    parts = [render_block(block, sources, numbers) for block in doc["content"]]
    if ai_share(doc) > 0:
        parts.append(f'<p class="otlet-mention-ia"><em>{escape(mention)}</em></p>')
    if sources:
        items = "".join(
            f"<li>{render_source(source)}</li>" for source in doc["attrs"]["sources"]
        )
        parts.append(
            f'<h2 class="otlet-sources-title">{SOURCES_TITLE}</h2>'
            f'<ol class="otlet-sources">{items}</ol>'
        )
    return "\n".join(parts)


def render_source(source: Node) -> str:
    details = ", ".join(escape(v) for v in (source.get("editeur"), source.get("date")) if v)
    link = f'<a href="{escape(source["url"])}">{escape(source["titre"])}</a>'
    return f"{link}, {details}" if details else link


def render_block(block: Node, sources: dict[str, Node], numbers: dict[str, int]) -> str:
    kind = block["type"]
    if kind in ("heading", "paragraph"):
        inline = render_inline(block.get("content", []), numbers)
    if kind == "heading":
        level = block["attrs"]["level"]
        return f"<h{level}>{inline}</h{level}>"
    if kind == "paragraph":
        return f"<p>{inline}</p>"
    if kind in ("bullet_list", "ordered_list"):
        return render_list(block, numbers)
    if kind == "citation":
        source = sources[block["attrs"]["source"]]
        paragraphs = "".join(
            f"<p>{render_inline(p.get('content', []), numbers)}</p>" for p in block["content"]
        )
        attribution = (
            f'<p class="otlet-citation-source">— <a href="{escape(source["url"])}">'
            f"{escape(source['titre'])}</a></p>"
        )
        return f'<blockquote class="otlet-citation">{paragraphs}{attribution}</blockquote>'
    if kind == "encadre":
        paragraphs = "".join(
            f"<p>{render_inline(p.get('content', []), numbers)}</p>" for p in block["content"]
        )
        return f'<aside class="otlet-encadre">{paragraphs}</aside>'
    if kind == "image":
        attrs = block["attrs"]
        return f'<figure><img src="{escape(attrs["media"])}" alt="{escape(attrs["alt"])}"></figure>'
    if kind == "separateur":
        return "<hr>"
    raise ValueError(f"unknown block type {kind!r}")


def render_list(node: Node, numbers: dict[str, int]) -> str:
    tag = "ul" if node["type"] == "bullet_list" else "ol"
    items = []
    for item in node["content"]:
        inner = []
        for child in item["content"]:
            if child["type"] == "paragraph":
                inner.append(f"<p>{render_inline(child.get('content', []), numbers)}</p>")
            else:
                inner.append(render_list(child, numbers))
        items.append(f"<li>{''.join(inner)}</li>")
    return f"<{tag}>{''.join(items)}</{tag}>"


def render_inline(content: list[Node], numbers: dict[str, int]) -> str:
    out = []
    for node in content:
        text = escape(node["text"], quote=False)
        marks = {m["type"]: m.get("attrs", {}) for m in node.get("marks", [])}
        if "bold" in marks:
            text = f"<strong>{text}</strong>"
        if "italic" in marks:
            text = f"<em>{text}</em>"
        if "link" in marks:
            text = f'<a href="{escape(marks["link"]["href"])}">{text}</a>'
        if "source_ref" in marks:
            number = numbers[marks["source_ref"]["source"]]
            text = f'{text}<sup class="otlet-source-ref">[{number}]</sup>'
        out.append(text)
    return "".join(out)
