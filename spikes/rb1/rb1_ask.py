# SPDX-License-Identifier: AGPL-3.0-or-later
"""RB1, phase 1 (docs/spikes/RB1.md §3): each question in Joël's Reporter, on the items of the
corpus dates, then « Trie-les » twice. Through the worker's code, one call at a time.

Run in the worker container, data folder mounted on /data:
    python /data/rb1_ask.py        -> /data/ask.jsonl (one line per question; resumes)
"""

import dataclasses
import json
import sys
import time
from datetime import date
from pathlib import Path
from uuid import UUID

from otlet.ai.adapters.jobs import gateway
from otlet.assistant.adapters.ai_model import GatewayModel
from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.jobs.application.registry import JobEnvironment
from otlet.meaning.adapters.encoder import encode_question
from otlet.platform import database
from otlet.platform.config import Settings
from otlet.reporter.adapters.postgres import PostgresReporterStore
from otlet.reporter.application.reporter import Reporter

WS = UUID("0150f5a4-a6bf-40db-ba7a-256b75d6d412")
USER = UUID("1fd3f00a-87b4-4473-aaf9-db737556c1b8")
DATA = Path("/data")
SPEC = json.load((DATA / "questions.json").open(encoding="utf-8"))
DATES = (date.fromisoformat(SPEC["corpus"]["from"]), date.fromisoformat(SPEC["corpus"]["to"]))
OUT = DATA / "ask.jsonl"

settings = Settings.from_env()
engine = database.create_engine(settings.require_database_url())
env = JobEnvironment(engine, secrets_private_key_file=settings.secrets_private_key_file)
store = PostgresReporterStore(engine, lambda *a, **k: None)
search = PostgresAssistantStore(engine)
done = {json.loads(line)["n"] for line in OUT.open(encoding="utf-8")} if OUT.exists() else set()


def run(conversation_id, question, dates=(None, None)):
    turn = store.add_turn(WS, USER, conversation_id, question, False, dates)
    model = GatewayModel(gateway(env), "reporter", cancelled=lambda: False)
    began = time.monotonic()
    Reporter(store, search, model, encode=encode_question).run(WS, USER, conversation_id, turn.id)
    found = store.conversation(WS, conversation_id).turns[-1]
    return found, round(time.monotonic() - began)


def verdicts(turn):
    return {str(i): [j.verdict.value, j.reason] for i, j in (turn.verdicts or {}).items()}


for spec in SPEC["questions"]:
    if spec["n"] in done:
        continue
    conversation = store.start_conversation(WS, USER, f"[RB1] {spec['q']}"[:100], None)
    first, s1 = run(conversation.id, spec["q"], DATES)
    sorts = []
    if first.candidates:
        for _ in range(2):
            time.sleep(10)
            sorted_turn, seconds = run(conversation.id, "Trie-les")
            sorts.append({"status": sorted_turn.status, "error": sorted_turn.error,
                          "seconds": seconds, "verdicts": verdicts(sorted_turn)})
    record = {
        "n": spec["n"], "q": spec["q"], "conv": str(conversation.id),
        "status": first.status, "error": first.error, "seconds": s1,
        "operation": str(first.operation),
        "concepts": [[w.concept.name, list(w.concept.terms)] for w in first.concepts],
        "fact": json.loads(json.dumps(dataclasses.asdict(first.fact), default=str)) if first.fact else None,
        "candidates": [
            {"id": str(c.id), "title": c.title, "summary": c.summary[:300], "publisher": c.publisher,
             "dated": c.dated.isoformat()}
            for c in first.candidates
        ],
        "sorts": sorts,
    }
    with OUT.open("a", encoding="utf-8") as out:
        out.write(json.dumps(record, ensure_ascii=False) + chr(10))
    print(spec["n"], first.status, len(first.candidates), [s["seconds"] for s in sorts], flush=True)
    time.sleep(20)
print("finished", flush=True)
sys.exit(0)
