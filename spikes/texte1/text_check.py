# SPDX-License-Identifier: AGPL-3.0-or-later
"""Does the text kept for an item speak of its title? Read only, no model of Ollama. Run in the
worker container. Two signals, written before reading the results: the words of the title and of
the summary found in the text, then the closeness (MiniLM) of the text to title + summary. A JSON
line per suspect, then a line per source and one of totals."""

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from uuid import UUID

import sqlalchemy as sa

from otlet.meaning.adapters.encoder import OnnxEncoder
from otlet.platform import database
from otlet.platform.config import Settings
from otlet.platform.database import workspace_transaction

WS = UUID("0150f5a4-a6bf-40db-ba7a-256b75d6d412")
STOP = set(
    """dans pour avec sans plus cette ces leur leurs nous vous elle elles ils sont être etre avoir
    mais comme aussi tout tous toute toutes très tres quoi dont que qui des les une un sur par
    voici pourquoi comment quand après apres avant deux trois
    voor naar door over zijn wordt niet maar deze the and for with from that this have will""".split()
)


def words(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    bare = "".join(c for c in folded if not unicodedata.combining(c))
    return {w[:6] for w in re.findall(r"[a-z0-9]{4,}", bare) if w not in STOP}


def share(part: set[str], whole: set[str]) -> float:
    return len(part & whole) / len(part) if part else 1.0


engine = database.create_engine(Settings.from_env().require_database_url())
with workspace_transaction(engine, WS) as c:
    rows = c.execute(sa.text(
        "SELECT i.id, i.title, i.summary, i.text, i.text_status, i.url, i.language,"
        " coalesce(i.published_at, i.collected_at) AS dated, coalesce(s.name, 'manuel') AS source"
        " FROM source_items i LEFT JOIN sources s ON s.id = i.source_id"
        " WHERE i.duplicate_of IS NULL AND i.text_status IN ('full_text', 'manual')"
        " AND i.text IS NOT NULL")).all()

totals: Counter = Counter()
by_source: dict[str, Counter] = defaultdict(Counter)
flagged = []
for row in rows:
    body = words(row.text)
    title = share(words(row.title), body)
    summary = share(words(row.summary or ""), body)
    size = len(row.text)
    totals["items"] += 1
    by_source[row.source]["items"] += 1
    by_source[row.source]["chars"] += size
    if size < 800:
        by_source[row.source]["short"] += 1
    # Few words of the title and few of the summary: a candidate, to be confirmed by the meaning.
    if title < 0.34 and summary < 0.34:
        flagged.append((row, title, summary))

encoder = OnnxEncoder()
controls = rows[:: max(1, len(rows) // 300)]


def closeness(row) -> float:  # type: ignore[no-untyped-def]
    head, body = encoder.encode([f"{row.title} {(row.summary or '')[:300]}", row.text[:600]])
    return float(sum(a * b for a, b in zip(head, body, strict=True)))


control = sorted(closeness(r) for r in controls)
print(json.dumps({"controls": len(control), "p05": control[len(control) // 20], "p50": control[len(control) // 2]}))
for row, title, summary in flagged:
    near = closeness(row)
    by_source[row.source]["flagged"] += 1
    totals["flagged"] += 1
    if near < 0.4:
        by_source[row.source]["confirmed"] += 1
        totals["confirmed"] += 1
    print(json.dumps({
        "id": str(row.id), "source": row.source, "status": row.text_status, "size": len(row.text),
        "title_share": round(title, 2), "summary_share": round(summary, 2), "near": round(near, 2),
        "dated": row.dated.date().isoformat(), "url": row.url, "title": row.title[:90],
        "text": row.text[:110].replace("\n", " "),
    }, ensure_ascii=False), flush=True)
for name, count in sorted(by_source.items(), key=lambda kv: -kv[1]["flagged"]):
    print(json.dumps({"by_source": name, **count}, ensure_ascii=False))
print(json.dumps({"totals": totals}))
print("finished", file=sys.stderr)
