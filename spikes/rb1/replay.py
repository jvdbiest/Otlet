# SPDX-License-Identifier: AGPL-3.0-or-later
"""RB1 correction 1, read only and without a model: the stored concepts of every question of the
Reporter, guarded again by the new rules (PYTHONPATH = the new src) and by the deployed ones.
For each question whose concepts change, the same search before and after: its set size, and
for the RB1 questions the R items found (questions.json).

Run in the worker container, the new src on /new and this folder on /data:
    PYTHONPATH=/new python /data/replay.py  -> one JSON line per changed question, then totals
"""

import importlib.util
import json
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import UUID

import sqlalchemy as sa

from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.assistant.domain.fusion import NEAR_FLOOR, fused, widely_near
from otlet.assistant.domain.terms import Concept, too_general, widen
from otlet.platform import database
from otlet.platform.config import Settings
from otlet.platform.database import workspace_transaction
from otlet.reporter.domain.questions import Operation, Translated, guarded

_spec = importlib.util.spec_from_file_location(
    "deployed_questions",
    "/opt/otlet/venv/lib/python3.13/site-packages/otlet/reporter/domain/questions.py",
)
deployed = importlib.util.module_from_spec(_spec)
sys.modules["deployed_questions"] = deployed
_spec.loader.exec_module(deployed)

WS = UUID("0150f5a4-a6bf-40db-ba7a-256b75d6d412")
SPEC = {q["q"]: q for q in json.load(open("/data/questions.json", encoding="utf-8"))["questions"]}
engine = database.create_engine(Settings.from_env().require_database_url())
store = PostgresAssistantStore(engine)

with workspace_transaction(engine, WS) as c:
    turns = c.execute(sa.text(
        "SELECT t.question, t.created_at, t.state, c.days, t.operation, t.position"
        " FROM reporter_turns t JOIN reporter_conversations c ON c.id = t.conversation_id"
        " WHERE t.status = 'done' AND t.position = 1 ORDER BY t.created_at DESC"
    )).all()


def search(concepts, since, until, meaning):
    w = widen(concepts, [])
    counts = store.term_counts(WS, [t for x in w for t in x.all_terms], since)
    w = too_general(w, counts, store.total_items(WS, since))
    words = store.candidates(WS, w, since, 200, until)
    scored = store.closest(WS, tuple(meaning), since, 60, until)
    near = widely_near(scored) if words else [c for c, s in scored if s >= NEAR_FLOOR]
    return fused([words, near], lambda c: c.id, 200)


seen = set()
totals = {"questions": 0, "changed": 0}
for t in turns:
    key = t.question.strip().casefold()
    concepts = [Concept(x["name"], tuple(x["terms"])) for x in t.state.get("concepts", [])]
    if key in seen or not concepts or t.operation not in {o.value for o in Operation}:
        continue
    seen.add(key)
    totals["questions"] += 1
    today = t.created_at.date()
    raw = tuple(concepts)
    new = guarded(t.question, Translated(Operation(t.operation), raw, None), today).concepts
    was = deployed.guarded(
        t.question, deployed.Translated(deployed.Operation(t.operation), raw, None), today
    ).concepts
    if new == was:
        continue
    totals["changed"] += 1
    days = t.state.get("days") or t.days or 30
    since, until = t.created_at - timedelta(days=days), t.created_at
    if t.question in SPEC:
        # The RB1 questions were asked on the two days of the corpus (the calendar).
        since = datetime(2026, 11, 7, tzinfo=ZoneInfo("Europe/Brussels"))
        until = datetime(2026, 11, 9, tzinfo=ZoneInfo("Europe/Brussels"))
    meaning = t.state.get("meaning")
    line = {"q": t.question, "before_c": [c.name for c in was], "after_c": [c.name for c in new]}
    if meaning:
        before = search(list(was), since, until, meaning)
        after = search(list(new), since, until, meaning)
        line.update({"set_before": len(before), "set_after": len(after)})
        spec = SPEC.get(t.question)
        if spec and spec["R"]:
            r = lambda items: sum(any(re.search(p, i.title, re.I) for p in spec["R"]) for i in items)  # noqa: E731
            line.update({"R_before": r(before), "R_after": r(after)})
    print(json.dumps(line, ensure_ascii=False), flush=True)
print(json.dumps(totals))
