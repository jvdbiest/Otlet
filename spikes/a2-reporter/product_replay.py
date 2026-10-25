# SPDX-License-Identifier: AGPL-3.0-or-later
"""A2-1 check: the twelve conversations of the bench replayed through the Reporter of the
product (otlet.reporter), on the Veille of a workspace, with a model of Ollama. The
conversations are kept in memory: nothing is written in the workspace.

Appended to replay.py and run in the worker container:
  cat replay.py product_replay.py | docker compose exec -T -e A2_BENCH=1 worker python - <workspace>
"""

import json
import os
import time
import urllib.request
from dataclasses import replace as _replace
from uuid import uuid4

from otlet.assistant.application.dossiers import Asked
from otlet.reporter.application.reporter import Conversation, Reporter, Turn
from otlet.reporter.adapters.postgres import PostgresReporterStore

OLLAMA = os.environ.get("OLLAMA", "http://192.168.129.45:11434")
MODEL = os.environ.get("MODEL", "qwen3:14b")


class OllamaModel:
    def ask(self, user_id, system, user, schema, validate, max_output_tokens):  # type: ignore[no-untyped-def]
        body = json.dumps({
            "model": MODEL, "stream": False, "think": False, "format": schema,
            "options": {"temperature": 0, "num_ctx": 16384, "num_predict": max_output_tokens},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode()
        started = time.monotonic()
        request = urllib.request.Request(f"{OLLAMA}/api/chat", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=900) as response:
            text = json.load(response)["message"]["content"]
        seconds = round(time.monotonic() - started, 1)
        errors = validate(text)
        return Asked(None if errors else text, "; ".join(errors) or None, MODEL, ({"seconds": seconds},))


class MemoryStore:
    """The conversations in memory; the articles read from the database."""

    def __init__(self, database: PostgresReporterStore) -> None:
        self._database = database
        self._conversations: dict = {}

    def start_conversation(self, workspace_id, user_id, title, days):  # type: ignore[no-untyped-def]
        conversation = Conversation(uuid4(), title, days)
        self._conversations[conversation.id] = conversation
        return conversation

    def conversations(self, workspace_id, user_id, limit):  # type: ignore[no-untyped-def]
        return list(self._conversations.values())

    def conversation(self, workspace_id, conversation_id):  # type: ignore[no-untyped-def]
        return self._conversations.get(conversation_id)

    def add_turn(self, workspace_id, user_id, conversation_id, question):  # type: ignore[no-untyped-def]
        conversation = self._conversations[conversation_id]
        turn = Turn(uuid4(), len(conversation.turns) + 1, question, "pending")
        self._conversations[conversation_id] = _replace(conversation, turns=[*conversation.turns, turn])
        return turn

    def save_turn(self, workspace_id, conversation_id, turn):  # type: ignore[no-untyped-def]
        conversation = self._conversations[conversation_id]
        turns = [turn if t.id == turn.id else t for t in conversation.turns]
        self._conversations[conversation_id] = _replace(conversation, turns=turns)

    def articles(self, workspace_id, item_ids):  # type: ignore[no-untyped-def]
        return self._database.articles(workspace_id, item_ids)


def product_replay(workspace: UUID) -> None:
    from otlet.workspaces.domain.model import Role, WorkspaceContext

    engine = db.create_engine(Settings.from_env().require_database_url())
    store = MemoryStore(PostgresReporterStore(engine))
    search = PostgresAssistantStore(engine)
    user = uuid4()
    context = WorkspaceContext(user_id=user, workspace_id=workspace, role=Role.OWNER)
    reporter = Reporter(store, search, OllamaModel())
    only = os.environ.get("ONLY")
    for key, steps in CONVERSATIONS:
        if only and key not in only.split(","):
            continue
        print(f"\n=================== Conversation {key}")
        conversation = None
        for question, expected, *_ in steps:
            started = time.monotonic()
            if conversation is None:
                conversation = reporter.start(context, question)
                turn = conversation.turns[0]
            else:
                turn = reporter.ask(context, conversation.id, question)
            reporter.run(workspace, user, conversation.id, turn.id)
            done = store.conversation(workspace, conversation.id).turns[-1]
            seconds = round(time.monotonic() - started, 1)
            terms = [list(w.terms) for w in done.concepts]
            print(f"--- {question} | attendu {expected} | {done.status} {done.operation and done.operation.value}"
                  f" ({seconds} s) | {len(done.candidates)} articles | langue {done.state.language} | {terms}")
            if done.error:
                print(f"    erreur : {done.error}")
            if done.fact is not None:
                fact = done.fact
                print(f"    fait : {fact.agreement.value} ({len(fact.lines)} lignes, {fact.dropped} écartées) — {fact.conclusion}")
                for line in fact.lines:
                    print(f"      {line.publisher} | {line.figure} | {line.measure} | {line.when} | {line.where}"
                          f"{'' if line.figure_in_passage else ' | HORS EXTRAIT'}")
                for c in fact.compared:
                    a, b = fact.lines[c.first], fact.lines[c.second]
                    print(f"      comparé : {a.publisher} {a.figure} {'=' if c.same else '≠'} {b.publisher} {b.figure}")


product_replay(UUID(sys.argv[1]))
