# SPDX-License-Identifier: AGPL-3.0-or-later
"""Real trial with Joël's own model, one question at a time, through the worker's code. Each question
is a new conversation « [Banc recherche] … » in his Reporter list. One JSON line per question."""
import json
import time
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
QUESTIONS = [
    "Pourquoi risque t'il de faire très froid dans les jours qui viennent ?",
    "Quelles sont les dernières actualités concernant l'Ukraine ?",
    "La situation financière des hôpitaux en Flandre",
    "Les pertes d'emploi en Belgique",
    "Les essais de motos récents",
    "Que rachète Ahold Delhaize ?",
    "Les élevages de lamas sur la planète Mars",
    "Les prix de l'énergie risquent-ils d'augmenter cet hiver ?",
]
settings = Settings.from_env()
engine = database.create_engine(settings.require_database_url())
env = JobEnvironment(engine, secrets_private_key_file=settings.secrets_private_key_file)
store = PostgresReporterStore(engine, lambda *a, **k: None)
search = PostgresAssistantStore(engine)
for question in QUESTIONS:
    started = time.monotonic()
    conversation = store.start_conversation(WS, USER, f"[Banc recherche] {question}"[:100], 30)
    turn = store.add_turn(WS, USER, conversation.id, question, False)
    model = GatewayModel(gateway(env), "reporter", cancelled=lambda: False)
    Reporter(store, search, model, encode=encode_question).run(WS, USER, conversation.id, turn.id)
    done = store.conversation(WS, conversation.id).turns[-1]
    print(json.dumps({
        "q": question, "conv": str(conversation.id), "status": done.status, "error": done.error,
        "op": str(done.operation), "seconds": round(time.monotonic() - started),
        "concepts": [[w.concept.name, list(w.concept.terms)] for w in done.concepts],
        "n": len(done.candidates), "titles": [c.title for c in done.candidates],
    }, ensure_ascii=False), flush=True)
    time.sleep(20)
