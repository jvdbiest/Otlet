# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read only, no model. New rules over the concepts stored for every first question: before and
after, the same search. Run with PYTHONPATH=/tmp/recherche/src in the worker container. Also lists
every turn whose concepts the new guard changes."""
import json
import sys
from datetime import date, timedelta
from uuid import UUID

import sqlalchemy as sa

from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.assistant.domain.fusion import NEAR_FLOOR, fused, widely_near
from otlet.assistant.domain.terms import Concept, too_general, widen
from otlet.platform import database
from otlet.platform.config import Settings
from otlet.platform.database import workspace_transaction
from otlet.reporter.domain.questions import Operation, Translated, guarded

import importlib.util
_spec = importlib.util.spec_from_file_location("old_questions", "/opt/otlet/venv/lib/python3.13/site-packages/otlet/reporter/domain/questions.py")
old = importlib.util.module_from_spec(_spec); sys.modules["old_questions"] = old; _spec.loader.exec_module(old)

WS = UUID("0150f5a4-a6bf-40db-ba7a-256b75d6d412")
engine = database.create_engine(Settings.from_env().require_database_url())
store = PostgresAssistantStore(engine)

with workspace_transaction(engine, WS) as c:
    turns = c.execute(sa.text(
        "SELECT t.question, t.created_at, t.state, c.days, t.operation, t.position"
        " FROM reporter_turns t JOIN reporter_conversations c ON c.id = t.conversation_id"
        " WHERE t.status = 'done' ORDER BY t.created_at DESC")).all()


def search(concepts, since, until, meaning):
    w = widen(concepts, [])
    counts = store.term_counts(WS, [t for x in w for t in x.all_terms], since)
    w = too_general(w, counts, store.total_items(WS, since))
    words = store.candidates(WS, w, since, 200, until)
    scored = store.closest(WS, tuple(meaning), since, 60, until)
    return words, scored


def dump(items):
    return [{"id": str(x.id), "t": x.title, "s": x.summary} for x in items]


seen, changed = set(), []
for t in turns:
    concepts = [Concept(x["name"], tuple(x["terms"])) for x in t.state.get("concepts", [])]
    if not concepts or t.operation not in {o.value for o in Operation}:
        continue
    new = guarded(t.question, Translated(Operation(t.operation), tuple(concepts), None), t.created_at.date()).concepts
    was = old.guarded(t.question, old.Translated(old.Operation(t.operation), tuple(concepts), None), t.created_at.date()).concepts
    new = new if new != was else tuple(concepts)
    if new != tuple(concepts):
        changed.append({"q": t.question, "pos": t.position, "op": t.operation, "before": [c.name for c in concepts], "after": [c.name for c in new]})
    key = t.question.strip().casefold()
    if t.position != 1 or key in seen or not t.state.get("meaning"):
        continue
    seen.add(key)
    days = t.state.get("days") or t.days or 30
    since, until = t.created_at - timedelta(days=days), t.created_at
    before, scored = search(concepts, since, until, t.state["meaning"])
    after, _ = search(list(new), since, until, t.state["meaning"]) if list(new) != concepts else (before, None)
    strict = [c for c, s in scored if s >= NEAR_FLOOR]
    near_new = widely_near(scored) if after else strict
    set_before = fused([before, strict], lambda c: c.id, 200)
    set_after = fused([after, near_new], lambda c: c.id, 200)
    print(json.dumps({
        "q": t.question, "before_c": [c.name for c in concepts], "after_c": [c.name for c in new],
        "before": dump(set_before), "after": dump(set_after), "best": scored[0][1] if scored else None,
        "words_before": len(before), "words_after": len(after), "near_before": len(strict), "near_after": len(near_new),
    }, ensure_ascii=False), flush=True)
print(json.dumps({"changed": changed}, ensure_ascii=False))
