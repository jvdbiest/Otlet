# SPDX-License-Identifier: AGPL-3.0-or-later
"""TEXTE1b: the frozen pages. Up to 40 texts per site with 70 texts or more, among the items whose
text the rules allowed (`full_text`), read again as the worker reads them, one every 3 s. Writes
nothing in the Veille. One JSON line per page on stdout, the page gzipped: it stays on the VM."""

import base64
import gzip
import json
import time
from uuid import UUID

import sqlalchemy as sa

from otlet.platform import database
from otlet.platform.config import Settings
from otlet.platform.database import workspace_transaction
from otlet.platform.http import SafeClient

WS = UUID("0150f5a4-a6bf-40db-ba7a-256b75d6d412")
PER_SITE = 40
SITE_MIN = 70
engine = database.create_engine(Settings.from_env().require_database_url())
with workspace_transaction(engine, WS) as c:
    c.execute(sa.text("SELECT setseed(0.1101)"))
    rows = c.execute(sa.text(
        "WITH texts AS (SELECT i.id, i.title, i.summary, i.url, i.text, s.name AS source,"
        " count(*) OVER (PARTITION BY s.name) AS site,"
        " row_number() OVER (PARTITION BY s.name ORDER BY random()) AS pick"
        " FROM source_items i JOIN sources s ON s.id = i.source_id WHERE i.duplicate_of IS NULL"
        " AND i.text_status = 'full_text' AND i.text IS NOT NULL AND i.url IS NOT NULL"
        " AND i.collected_at > now() - interval '30 days')"
        " SELECT * FROM texts WHERE site >= :least AND pick <= :per ORDER BY random()"),
        {"least": SITE_MIN, "per": PER_SITE}).all()
with SafeClient() as client:
    for row in rows:
        out = {
            "id": str(row.id), "source": row.source, "site_texts": row.site, "url": row.url,
            "title": row.title, "summary": row.summary, "stored": row.text,
        }
        try:
            page = client.get(row.url, max_bytes=5_000_000)
            out |= {
                "status": page.status, "final_url": page.url, "type": page.content_type,
                "html": base64.b64encode(gzip.compress(page.text().encode("utf-8"))).decode(),
            }
        except Exception as error:  # noqa: BLE001 (a frozen page, or why there is none)
            out["error"] = repr(error)[:160]
        print(json.dumps(out, ensure_ascii=False), flush=True)
        time.sleep(3)
print(json.dumps({"finished": True}), flush=True)
