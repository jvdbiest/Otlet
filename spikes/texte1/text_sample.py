# SPDX-License-Identifier: AGPL-3.0-or-later
"""How much of the article does the stored text hold? A random sample of the texts of the last 30
days, the page read again as the worker reads it, one every 3 s. Writes nothing; pages stay in
memory. The article, by the first signal that exists: articleBody, else the long paragraphs of the
largest <article>, else all the long paragraphs of the page. One JSON line per item."""

import json
import re
import time
from uuid import UUID

import lxml.html
import sqlalchemy as sa

from otlet.collection.adapters.parsing import ReadabilityReader, clean_text
from otlet.platform import database
from otlet.platform.config import Settings
from otlet.platform.database import workspace_transaction
from otlet.platform.http import SafeClient

WS = UUID("0150f5a4-a6bf-40db-ba7a-256b75d6d412")
SAMPLE = 120
engine = database.create_engine(Settings.from_env().require_database_url())
reader = ReadabilityReader()
with workspace_transaction(engine, WS) as c:
    c.execute(sa.text("SELECT setseed(0.2026)"))
    rows = c.execute(sa.text(
        "SELECT i.id, i.title, i.url, i.text, coalesce(s.name, 'manuel') AS source FROM source_items i"
        " LEFT JOIN sources s ON s.id = i.source_id WHERE i.duplicate_of IS NULL"
        " AND i.text_status = 'full_text' AND i.text IS NOT NULL AND i.url IS NOT NULL"
        " AND i.collected_at > now() - interval '30 days' ORDER BY random() LIMIT :n"), {"n": SAMPLE}).all()


def long_paragraphs(node) -> int:  # type: ignore[no-untyped-def]
    return sum(len(t) for t in (p.text_content().strip() for p in node.iter("p")) if len(t) > 80)


with SafeClient() as client:
    for row in rows:
        out = {"source": row.source, "title": row.title[:70], "stored": len(row.text)}
        try:
            page = client.get(row.url, max_bytes=5_000_000)
            html = page.text()
            tree = lxml.html.fromstring(html)
            extracted = reader.extract(html, page.url)
            body = max((len(b) for b in re.findall(r'"articleBody"\s*:\s*"((?:[^"\\]|\\.)*)"', html)), default=0)
            article = max((long_paragraphs(a) for a in tree.iter("article")), default=0)
            whole = long_paragraphs(tree)
            out |= {
                "status": page.status, "again": len(extracted.text) if extracted else 0,
                "same": bool(extracted) and clean_text(extracted.text) == clean_text(row.text),
                "articleBody": body, "article": article, "whole": whole,
                "best": body if body >= 200 else article if article >= 200 else whole,
            }
        except Exception as error:  # noqa: BLE001 (a probe: say what happened and go on)
            out["error"] = repr(error)[:120]
        print(json.dumps(out, ensure_ascii=False), flush=True)
        time.sleep(3)
print(json.dumps({"finished": True}), flush=True)
