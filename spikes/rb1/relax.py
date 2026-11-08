# SPDX-License-Identifier: AGPL-3.0-or-later
"""RB1 §9, read only and without a model: when the concepts required together find fewer than 3
items, rules R1 (relax by frequency), R2 (meaning alone) and R3 (R1 then R2) against R0 (the
product), on the stored concepts of the first question of every Reporter conversation.

Run in the worker container, this folder on /data:  python /data/relax.py  -> relax.jsonl lines
"""

import json
import re
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.assistant.domain.fusion import NEAR_FLOOR, NEAR_MAX, fused, widely_near
from otlet.assistant.domain.terms import Concept, too_general, widen
from otlet.platform import database
from otlet.platform.config import Settings
from otlet.platform.database import workspace_transaction
from otlet.reporter.domain.questions import folded, is_place, proper_names

WS = UUID("0150f5a4-a6bf-40db-ba7a-256b75d6d412")
FEW = 3
SPEC = {q["q"]: q for q in json.load(open("/data/questions.json", encoding="utf-8"))["questions"]}
engine = database.create_engine(Settings.from_env().require_database_url())
store = PostgresAssistantStore(engine)

with workspace_transaction(engine, WS) as c:
    turns = c.execute(sa.text(
        "SELECT t.question, t.created_at, t.state, c.days, c.title"
        " FROM reporter_turns t JOIN reporter_conversations c ON c.id = t.conversation_id"
        " WHERE t.status = 'done' AND t.position = 1 ORDER BY t.created_at DESC"
    )).all()


def words(concepts, since, until):
    if not concepts:
        return []
    w = widen(concepts, [])
    counts = store.term_counts(WS, [t for x in w for t in x.all_terms], since)
    w = too_general(w, counts, store.total_items(WS, since))
    return store.candidates(WS, w, since, 200, until)


def frequency(concept, since):
    counts = store.term_counts(WS, list(concept.terms), since)
    return sum(counts.values())


def protected(question, concept):
    names = {folded(w) for n in proper_names(question) for w in n.split()}
    return is_place(concept) or bool(names & {folded(w) for w in re.findall(r"[\w'-]+", concept.name)})


def relaxed(question, concepts, since, until):
    concepts = list(concepts)
    found = words(concepts, since, until)
    dropped = []
    while len(found) < FEW and len(concepts) > 1:
        free = [c for c in concepts if not protected(question, c)]
        if not free:
            break
        most = max(free, key=lambda c: frequency(c, since))
        concepts.remove(most)
        dropped.append(most.name)
        found = words(concepts, since, until)
    return found, dropped


seen = set()
for t in turns:
    key = t.question.strip().casefold()
    concepts = [Concept(x["name"], tuple(x["terms"])) for x in t.state.get("concepts", [])]
    meaning = t.state.get("meaning")
    if key in seen or not concepts or not meaning:
        continue
    seen.add(key)
    days = t.state.get("days") or t.days or 30
    since, until = t.created_at - timedelta(days=days), t.created_at
    if t.question in SPEC:
        since = datetime(2026, 11, 7, tzinfo=ZoneInfo("Europe/Brussels"))
        until = datetime(2026, 11, 9, tzinfo=ZoneInfo("Europe/Brussels"))
    found0 = words(concepts, since, until)
    if len(found0) >= FEW:
        continue
    scored = store.closest(WS, tuple(meaning), since, NEAR_MAX, until)
    strict = [c for c, s in scored if s >= NEAR_FLOOR]
    wide = widely_near(scored)
    found1, dropped = relaxed(t.question, concepts, since, until)
    sets = {
        "R0": fused([found0, wide if found0 else strict], lambda c: c.id, 200),
        "R1": fused([found1, wide if found1 else strict], lambda c: c.id, 200),
        "R2": fused([found0, wide], lambda c: c.id, 200),
        "R3": fused([found1, wide], lambda c: c.id, 200),
    }
    line = {
        "title": t.title, "q": t.question, "concepts": [c.name for c in concepts],
        "dropped_R1": dropped, "best": round(scored[0][1], 3) if scored else None,
        "sizes": {k: len(v) for k, v in sets.items()},
        "top": {k: [i.title[:80] for i in v[:5]] for k, v in sets.items() if k != "R0"},
    }
    spec = SPEC.get(t.question)
    if spec and spec["R"]:
        line["R"] = {
            k: sum(any(re.search(p, i.title, re.I) for p in spec["R"]) for i in v)
            for k, v in sets.items()
        }
    print(json.dumps(line, ensure_ascii=False), flush=True)
