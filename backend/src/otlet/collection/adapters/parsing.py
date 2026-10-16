# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reading feeds and article pages (TECH_CHOICES §14): feedparser for RSS, Atom and JSON Feed,
readability-lxml for the main content of a page, nh3 to sanitise.

Everything that comes in is untrusted (ARCHITECTURE P3): the texts are reduced to plain text,
without markup, invisible elements or invisible Unicode characters, which are the usual
carriers of prompt injection (ARCHITECTURE §10.5).
"""

import calendar
import hashlib
import html
import json
import re
import time
import unicodedata
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import feedparser
import lxml.etree
import lxml.html
import nh3
from readability import Document

from otlet.collection.domain.model import URL_MAX_LENGTH, FeedEntry, Page, ParsedFeed

FEED_TYPES = frozenset(
    {
        "application/rss+xml",
        "application/atom+xml",
        "application/feed+json",
        "application/json",
        "application/rdf+xml",
    }
)
BLOCK_END = re.compile(r"</(p|div|li|h[1-6]|blockquote|pre|tr|section|article)\s*>|<br\s*/?>", re.I)
HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)
SUMMARY_MAX_LENGTH = 5000
TITLE_MAX_LENGTH = 500


def clean_text(value: str) -> str:
    """Plain text from untrusted HTML or text: no tags, entities decoded, invisible format
    characters (zero width, bidirectional controls) removed, blank lines collapsed."""
    with_breaks = BLOCK_END.sub("\n\n", value)
    stripped = html.unescape(nh3.clean(with_breaks, tags=set()))
    visible = "".join(
        char
        for char in unicodedata.normalize("NFC", stripped)
        if unicodedata.category(char) != "Cf" or char == "\n"
    )
    lines = (" ".join(line.split()) for line in visible.splitlines())
    paragraphs: list[str] = []
    for line in lines:
        if line or (paragraphs and paragraphs[-1]):
            paragraphs.append(line)
    return "\n".join(paragraphs).strip()


def _web_url(value: object) -> str | None:
    """A link of the feed, kept only when it is a web address: a `javascript:` or `data:` link
    must never reach the interface."""
    if not isinstance(value, str) or len(value) > URL_MAX_LENGTH:
        return None
    return value if urlsplit(value).scheme.lower() in ("http", "https") else None


def _date(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), UTC)
    return None


def _entry(entry: Any) -> FeedEntry | None:
    url = _web_url(entry.get("link"))
    title = clean_text(entry.get("title", ""))[:TITLE_MAX_LENGTH]
    summary = clean_text(entry.get("summary", "")) or None
    contents = [clean_text(c.get("value", "")) for c in entry.get("content", [])]
    content = max(contents, key=len, default="") or None
    if content is not None and summary is not None and len(content) <= len(summary):
        content = None  # the feed repeats its summary
    if not title and not url and not summary:
        return None
    guid = entry.get("id") or url
    if not guid:
        guid = "sha256:" + hashlib.sha256(f"{title}\n{summary}".encode()).hexdigest()
    return FeedEntry(
        guid=str(guid)[:2000],
        url=url,
        title=title or (summary or url or "")[:120],
        author=clean_text(entry.get("author", "")) or None,
        published_at=_date(entry),
        summary=None if summary is None else summary[:SUMMARY_MAX_LENGTH],
        content=content,
    )


def _json_feed(body: bytes, url: str) -> ParsedFeed | None:
    """A JSON Feed (jsonfeed.org, versions 1 and 1.1), which feedparser 6.0 does not read."""
    try:
        document = json.loads(body)
    except ValueError:
        return None
    if not isinstance(document, dict) or not str(document.get("version", "")).startswith(
        "https://jsonfeed.org/version/"
    ):
        return None
    entries = []
    for item in document.get("items", []):
        if not isinstance(item, dict):
            continue
        link = item.get("url")
        content = item.get("content_html") or item.get("content_text") or ""
        entry = _entry(
            {
                "id": item.get("id"),
                "link": urljoin(url, link) if isinstance(link, str) else None,
                "title": str(item.get("title", "")),
                "summary": str(item.get("summary", "")),
                "content": [{"value": str(content)}],
                "author": _json_author(item),
                "published_parsed": _iso(item.get("date_published") or item.get("date_modified")),
            }
        )
        if entry is not None:
            entries.append(entry)
    title = clean_text(str(document.get("title", "")))[:TITLE_MAX_LENGTH] or None
    home = document.get("home_page_url")
    return ParsedFeed(title=title, site_url=_web_url(home), entries=tuple(entries))


def _json_author(item: dict[str, Any]) -> str:
    authors = item.get("authors") or [item.get("author")]
    first = authors[0] if isinstance(authors, list) and authors else None
    return str(first.get("name", "")) if isinstance(first, dict) else ""


def _iso(value: object) -> time.struct_time | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).timetuple()
    except ValueError:
        return None


class _FeedLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        attributes = {name.lower(): (value or "").strip() for name, value in attrs}
        rel = attributes.get("rel", "").lower().split()
        kind = attributes.get("type", "").lower()
        if "alternate" in rel and kind in FEED_TYPES and attributes.get("href"):
            self.links.append(attributes["href"])


class FeedparserReader:
    def read(self, body: bytes, url: str) -> ParsedFeed | None:
        # Bytes only: feedparser never fetches anything by itself here.
        if body.lstrip()[:1] == b"{":
            return _json_feed(body, url)
        parsed = feedparser.parse(body, response_headers={"content-location": url})
        if not parsed.get("version") and not parsed.get("entries"):
            return None
        entries = tuple(e for e in map(_entry, parsed.entries) if e is not None)
        feed = parsed.get("feed", {})
        title = clean_text(feed.get("title", ""))[:TITLE_MAX_LENGTH] or None
        return ParsedFeed(title=title, site_url=_web_url(feed.get("link")), entries=entries)

    def discover(self, page: str, url: str) -> list[str]:
        finder = _FeedLinks()
        finder.feed(page)
        found = [urljoin(url, href) for href in finder.links]
        return list(dict.fromkeys(found))


INVISIBLE_TAGS = frozenset({"script", "style", "noscript", "template"})


def _hidden(element: Any) -> bool:
    if element.tag in INVISIBLE_TAGS:
        return True
    if element.get("hidden") is not None or element.get("aria-hidden") == "true":
        return True
    return bool(HIDDEN_STYLE.search(element.get("style") or ""))


def _drop_invisible(page: str) -> str:
    """The page without the elements a reader does not see."""
    try:
        tree = lxml.html.fromstring(page)
    except (lxml.etree.ParserError, ValueError):
        return page
    for element in [e for e in tree.iter() if isinstance(e.tag, str) and _hidden(e)]:
        element.drop_tree()
    return str(lxml.html.tostring(tree, encoding="unicode"))


class ReadabilityReader:
    def extract(self, page: str, url: str) -> Page | None:
        visible = _drop_invisible(page)
        try:
            document = Document(visible, url=url)
            content = document.summary(html_partial=True)
            title = clean_text(document.short_title() or "")[:TITLE_MAX_LENGTH] or None
        except (lxml.etree.ParserError, ValueError, TypeError):
            return None
        text = clean_text(content)
        return Page(title=title, text=text) if text else None
