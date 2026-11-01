# SPDX-License-Identifier: AGPL-3.0-or-later
"""Where does a wrong text come from? For a few items per source: the page read again as the worker
reads it (SafeClient, ReadabilityReader), compared with the stored text and with what the page
holds. Writes nothing. Pages stay in memory. One JSON line per item. Usage: python - ID ID …"""

import json
import re
import sys
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
engine = database.create_engine(Settings.from_env().require_database_url())
reader = ReadabilityReader()
with workspace_transaction(engine, WS) as c:
    rows = c.execute(sa.text(
        "SELECT id, title, summary, url, text FROM source_items WHERE id = ANY(CAST(:i AS uuid[]))"),
        {"i": sys.argv[1:]}).all()
with SafeClient() as client:
    for row in rows:
        out = {"title": row.title[:70], "stored": len(row.text or ""), "url": row.url[:70]}
        try:
            page = client.get(row.url, max_bytes=5_000_000)
            html = page.text()
            tree = lxml.html.fromstring(html)
            extracted = reader.extract(html, page.url)
            paragraphs = [p.text_content().strip() for p in tree.iter("p")]
            long = [p for p in paragraphs if len(p) > 80]
            ld = re.findall(r'"articleBody"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
            articles = [a.text_content() for a in tree.iter("article")]
            summary_head = " ".join((row.summary or "").split()[:6])
            out |= {
                "status": page.status, "html": len(html),
                "again": len(extracted.text) if extracted else 0,
                "same_as_stored": bool(extracted) and clean_text(extracted.text) == clean_text(row.text or ""),
                "paragraphs": sum(len(p) for p in long), "articleBody": max(map(len, ld), default=0),
                "article_tags": [len(a) for a in articles][:6],
                "summary_in_html": bool(summary_head) and summary_head in clean_text(html),
                "stored_head": (row.text or "")[:60].replace("\n", " "),
                "first_long_p": long[0][:90] if long else "",
            }
        except Exception as error:  # noqa: BLE001 (a probe: say what happened and go on)
            out["error"] = repr(error)[:160]
        print(json.dumps(out, ensure_ascii=False), flush=True)
        time.sleep(3)
