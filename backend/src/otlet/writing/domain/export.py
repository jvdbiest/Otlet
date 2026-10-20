# SPDX-License-Identifier: AGPL-3.0-or-later
"""Exports of a version (X03c, ADR-0036): a whole HTML page, Markdown and plain text, made from
the « Document plateforme v1 » on demand, never stored. Each carries the Sources block and the
AI mention, as the renderer inserts them; the PDF is printed from the HTML page, the DOCX built
by its adapter."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from html import escape
from typing import Any

from otlet.writing.domain.document import MENTION_IA, SOURCES_TITLE, ai_share, render

Node = dict[str, Any]

# The page of an export: the reading view of Otlet, on paper (A4) for the PDF and printing.
PAGE_CSS = """
@page { size: A4; margin: 2cm 2.2cm; }
html { color: #1d1d1b; background: #ffffff; }
body { margin: 0 auto; max-width: 46rem; padding: 2rem 1.5rem;
  font: 12pt/1.55 Georgia, 'DejaVu Serif', serif; }
h1 { font-size: 22pt; line-height: 1.2; margin: 0 0 1rem; }
h2, h3, h4 { clear: both; line-height: 1.25; margin: 1.4em 0 0.5em; }
h2 { font-size: 16pt; } h3 { font-size: 13.5pt; } h4 { font-size: 12pt; }
p { margin: 0 0 0.8em; }
a { color: #2f5d8a; }
figure { margin: 1em 0; }
img { max-width: 100%; height: auto; }
.otlet-source-ref { font-size: 0.75em; vertical-align: super; line-height: 0; }
.otlet-citation { margin: 1em 0; padding-left: 1em; border-left: 3px solid #b0b0a8; }
.otlet-citation blockquote { margin: 0; }
.otlet-citation-source { font-size: 0.9em; color: #5c5c57; }
.otlet-encadre { display: block; margin: 1em 0; padding: 0.8em 1em; background: #f2f2ee; }
.otlet-mention-ia { clear: both; margin-top: 2em; color: #5c5c57; font-size: 0.9em; }
.otlet-sources-title { font-size: 13pt; }
.otlet-sources { font-size: 0.9em; }
hr { border: none; border-top: 1px solid #b0b0a8; margin: 1.5em 0; clear: both; }
@media print { body { max-width: none; padding: 0; } a { color: inherit; } }
"""


def filename(title: str, extension: str) -> str:
    """A file name from the title: « Max Verstappen : un pilote » → max-verstappen-un-pilote.pdf"""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:80] or "article"
    return f"{slug}.{extension}"


def html_page(title: str, document: Node, media_url: Callable[[str], str]) -> str:
    """A whole HTML page: the title, the body with its Sources block and AI mention, the page's
    style. `media_url` gives each image its address (a data URL keeps the page whole)."""
    body = render(document, media_url=media_url)
    language = escape(str(document["attrs"].get("langue") or "fr"))
    return (
        f'<!doctype html>\n<html lang="{language}">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{escape(title)}</title>\n<style>{PAGE_CSS}</style>\n</head>\n<body>\n<article>\n"
        f"<h1>{escape(title)}</h1>\n{body}\n</article>\n</body>\n</html>\n"
    )


# --- Markdown -------------------------------------------------------------------------------

_MD_SPECIAL = re.compile(r"([\\`*_\[\]#<>|~])")


def _md_text(text: str) -> str:
    return _MD_SPECIAL.sub(r"\\\1", text)


def _md_inline(content: list[Node]) -> str:
    out = []
    for node in content:
        marks = {m["type"]: m.get("attrs") or {} for m in node.get("marks", [])}
        text = node["text"]
        if "source_ref" in marks:
            out.append(text)
            continue
        inner = _md_text(text.strip())
        if not inner:
            out.append(text)
            continue
        if "superscript" in marks:
            inner = f"<sup>{inner}</sup>"
        if "subscript" in marks:
            inner = f"<sub>{inner}</sub>"
        if "highlight" in marks:
            inner = f"<mark>{inner}</mark>"
        if "strike" in marks:
            inner = f"~~{inner}~~"
        if "italic" in marks:
            inner = f"*{inner}*"
        if "bold" in marks:
            inner = f"**{inner}**"
        if "link" in marks:
            inner = f"[{inner}]({marks['link']['href']})"
        # Markdown marks may not open or close on a space: they stay outside.
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        out.append(f"{lead}{inner}{trail}")
    return "".join(out)


def _md_list(node: Node, depth: int) -> list[str]:
    lines = []
    ordered = node["type"] == "ordered_list"
    for n, item in enumerate(node["content"], start=1):
        marker = f"{n}." if ordered else "-"
        pad = "    " * depth
        first = True
        for child in item["content"]:
            if child["type"] == "paragraph":
                text = _md_inline(child.get("content", []))
                lines.append(f"{pad}{marker} {text}" if first else f"{pad}    {text}")
                first = False
            else:
                lines.extend(_md_list(child, depth + 1))
    return lines


def markdown(title: str, document: Node, image_path: Callable[[str], str]) -> str:
    """The article in Markdown; `image_path` gives each image the path it is saved under."""
    sources = {s["id"]: s for s in document["attrs"]["sources"]}
    parts = [f"# {_md_text(title)}"]
    for block in document["content"]:
        kind = block["type"]
        if kind == "heading":
            parts.append("#" * block["attrs"]["level"] + " " + _md_inline(block.get("content", [])))
        elif kind == "paragraph":
            parts.append(_md_inline(block.get("content", [])))
        elif kind in ("bullet_list", "ordered_list"):
            parts.append("\n".join(_md_list(block, 0)))
        elif kind in ("citation", "encadre"):
            lines = [f"> {_md_inline(p.get('content', []))}" for p in block["content"]]
            if kind == "citation":
                source = sources.get(block["attrs"]["source"], {"titre": "?"})
                name = _md_text(source["titre"])
                cited = f"[{name}]({source['url']})" if source.get("url") else name
                lines.append(f">\n> — {cited}")
            parts.append("\n".join(lines))
        elif kind == "separateur":
            parts.append("---")
        elif kind == "image":
            alt = _md_text(block["attrs"].get("alt") or "")
            parts.append(f"![{alt}]({image_path(block['attrs']['media'])})")
    if ai_share(document) > 0:
        parts.append(f"*{MENTION_IA}*")
    if sources:
        parts.append(f"## {SOURCES_TITLE}")
        parts.append("\n".join(f"{n}. {_md_source(s)}" for n, s in enumerate(sources.values(), 1)))
    return "\n\n".join(parts) + "\n"


def _md_source(source: Node) -> str:
    name = _md_text(source["titre"])
    linked = f"[{name}]({source['url']})" if source.get("url") else name
    details = ", ".join(_md_text(v) for v in (source.get("editeur"), source.get("date")) if v)
    return f"{linked}, {details}" if details else linked


# --- Plain text -----------------------------------------------------------------------------


def _txt_inline(content: list[Node]) -> str:
    return "".join(node["text"] for node in content)


def _txt_list(node: Node, depth: int) -> list[str]:
    lines = []
    ordered = node["type"] == "ordered_list"
    for n, item in enumerate(node["content"], start=1):
        marker = f"{n}." if ordered else "-"
        pad = "  " * depth
        first = True
        for child in item["content"]:
            if child["type"] == "paragraph":
                text = _txt_inline(child.get("content", []))
                lines.append(f"{pad}{marker} {text}" if first else f"{pad}  {text}")
                first = False
            else:
                lines.extend(_txt_list(child, depth + 1))
    return lines


def text(title: str, document: Node) -> str:
    """The article in plain text: no formatting, images named by their description."""
    sources = {s["id"]: s for s in document["attrs"]["sources"]}
    parts = [title, "=" * min(len(title), 80)]
    for block in document["content"]:
        kind = block["type"]
        if kind == "heading":
            heading = _txt_inline(block.get("content", []))
            parts.append(f"{heading}\n{'-' * min(len(heading), 80)}")
        elif kind == "paragraph":
            parts.append(_txt_inline(block.get("content", [])))
        elif kind in ("bullet_list", "ordered_list"):
            parts.append("\n".join(_txt_list(block, 0)))
        elif kind in ("citation", "encadre"):
            lines = [_txt_inline(p.get("content", [])) for p in block["content"]]
            if kind == "citation":
                source = sources.get(block["attrs"]["source"], {"titre": "?"})
                lines = [f"« {' '.join(lines)} »", f"— {source['titre']}"]
            parts.append("\n".join(lines))
        elif kind == "separateur":
            parts.append("* * *")
        elif kind == "image":
            alt = block["attrs"].get("alt")
            parts.append(f"[Image : {alt}]" if alt else "[Image]")
    if ai_share(document) > 0:
        parts.append(MENTION_IA)
    if sources:
        listed = []
        for n, source in enumerate(sources.values(), 1):
            details = ", ".join(v for v in (source.get("editeur"), source.get("date")) if v)
            line = f"{n}. {source['titre']}" + (f", {details}" if details else "")
            listed.append(line + (f"\n   {source['url']}" if source.get("url") else ""))
        parts.append(f"{SOURCES_TITLE}\n" + "\n".join(listed))
    return "\n\n".join(parts) + "\n"
