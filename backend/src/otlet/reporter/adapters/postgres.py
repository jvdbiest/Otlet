# SPDX-License-Identifier: AGPL-3.0-or-later
"""The conversations of the Reporter on PostgreSQL, in the context of each workspace."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.assistant.application.assistant import Candidate
from otlet.assistant.domain.qualify import Judged, Verdict
from otlet.assistant.domain.terms import Concept, Widened
from otlet.jobs.application.registry import Enqueue, no_queue
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here
from otlet.reporter.application.reporter import ANSWER_TURN, Conversation, Turn
from otlet.reporter.domain.facts import Agreement, Article, Compared, Fact, FactLine
from otlet.reporter.domain.questions import PROMPT_VERSION, Operation, State

TURN_COLUMNS = (
    "id, position, question, status, operation, state, concepts, candidates, fact, verdicts,"
    " error, model, prompt_version, attempts, created_at, finished_at"
)


def _concept(data: dict[str, Any]) -> Concept:
    return Concept(data["name"], tuple(data["terms"]))


def _state_json(state: State) -> str:
    return json.dumps(
        {
            "concepts": [{"name": c.name, "terms": list(c.terms)} for c in state.concepts],
            "language": state.language,
        }
    )


def _concepts_json(concepts: list[Widened], counts: dict[str, int]) -> str:
    return json.dumps(
        [
            {
                "name": w.concept.name,
                "terms": list(w.concept.terms),
                "added": list(w.added),
                "general": list(w.general),
                "counts": {term: counts[term] for term in w.all_terms if term in counts},
            }
            for w in concepts
        ]
    )


def _candidates_json(candidates: list[Candidate]) -> str:
    return json.dumps(
        [
            {
                "id": str(c.id),
                "title": c.title,
                "summary": c.summary,
                "url": c.url,
                "language": c.language,
                "publisher": c.publisher,
                "dated": c.dated.isoformat(),
            }
            for c in candidates
        ]
    )


def _fact_json(fact: Fact | None) -> str | None:
    if fact is None:
        return None
    return json.dumps(
        {
            "lines": [
                {
                    "item_id": f.item_id,
                    "publisher": f.publisher,
                    "figure": f.figure,
                    "measure": f.measure,
                    "when": f.when,
                    "where": f.where,
                    "passage": f.passage,
                    "figure_in_passage": f.figure_in_passage,
                }
                for f in fact.lines
            ],
            "agreement": fact.agreement.value,
            "compared": [[c.first, c.second, c.same] for c in fact.compared],
            "conclusion": fact.conclusion,
            "dropped": fact.dropped,
            "read": list(fact.read),
        }
    )


def _fact(data: dict[str, Any] | None) -> Fact | None:
    if data is None:
        return None
    return Fact(
        lines=tuple(FactLine(**line) for line in data["lines"]),
        agreement=Agreement(data["agreement"]),
        compared=tuple(Compared(a, b, same) for a, b, same in data["compared"]),
        conclusion=data["conclusion"],
        dropped=data["dropped"],
        read=tuple(data["read"]),
    )


def _turn(row: sa.Row[Any]) -> Turn:
    return Turn(
        id=row.id,
        position=row.position,
        question=row.question,
        status=row.status,
        operation=None if row.operation is None else Operation(row.operation),
        state=State(
            tuple(_concept(c) for c in row.state.get("concepts", [])), row.state.get("language")
        ),
        concepts=[
            Widened(_concept(c), tuple(c["added"]), tuple(c.get("general", ())))
            for c in row.concepts
        ],
        term_counts={term: n for c in row.concepts for term, n in c.get("counts", {}).items()},
        candidates=[
            Candidate(
                id=UUID(c["id"]),
                title=c["title"],
                summary=c["summary"],
                url=c["url"],
                language=c["language"],
                publisher=c["publisher"],
                dated=datetime.fromisoformat(c["dated"]),
            )
            for c in row.candidates
        ],
        fact=_fact(row.fact),
        verdicts={
            UUID(key): Judged(Verdict(v["verdict"]), v["reason"], v["by_model"])
            for key, v in row.verdicts.items()
        },
        error=row.error,
        model=row.model,
        prompt_version=row.prompt_version,
        attempts=list(row.attempts),
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


class PostgresReporterStore:
    def __init__(self, engine: sa.Engine, enqueue: Enqueue = no_queue) -> None:
        self._engine = engine
        self._enqueue = enqueue

    def start_conversation(
        self, workspace_id: UUID, user_id: UUID, title: str, days: int | None
    ) -> Conversation:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO reporter_conversations (id, workspace_id, created_by, title, days)"
                    " VALUES (:id, :workspace, :user, :title, :days)"
                    " RETURNING id, title, days, created_at"
                ),
                {
                    "id": uuid4(),
                    "workspace": workspace_id,
                    "user": user_id,
                    "title": title,
                    "days": days,
                },
            ).one()
        return Conversation(row.id, row.title, row.days, row.created_at)

    def conversations(self, workspace_id: UUID, user_id: UUID, limit: int) -> list[Conversation]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT id, title, days, created_at FROM reporter_conversations"
                    f" WHERE created_by = :user AND {here()} ORDER BY created_at DESC LIMIT :limit"
                ),
                {"user": user_id, "limit": limit},
            ).all()
        return [Conversation(r.id, r.title, r.days, r.created_at) for r in rows]

    def conversation(self, workspace_id: UUID, conversation_id: UUID) -> Conversation | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "SELECT id, title, days, created_at FROM reporter_conversations"
                    f" WHERE id = :id AND {here()}"
                ),
                {"id": conversation_id},
            ).one_or_none()
            if row is None:
                return None
            turns = connection.execute(
                sa.text(
                    f"SELECT {TURN_COLUMNS} FROM reporter_turns"
                    f" WHERE conversation_id = :id AND {here()} ORDER BY position"
                ),
                {"id": conversation_id},
            ).all()
        return Conversation(row.id, row.title, row.days, row.created_at, [_turn(t) for t in turns])

    def add_turn(
        self, workspace_id: UUID, user_id: UUID, conversation_id: UUID, question: str
    ) -> Turn:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO reporter_turns (id, workspace_id, conversation_id, position,"
                    " question, prompt_version) SELECT :id, :workspace, :conversation,"
                    " coalesce(max(position), 0) + 1, :question, :version FROM reporter_turns"
                    f" WHERE conversation_id = :conversation AND {here()}"
                    f" RETURNING {TURN_COLUMNS}"
                ),
                {
                    "id": uuid4(),
                    "workspace": workspace_id,
                    "conversation": conversation_id,
                    "question": question,
                    "version": PROMPT_VERSION,
                },
            ).one()
            self._enqueue(
                connection,
                ANSWER_TURN,
                workspace_id=str(workspace_id),
                user_id=str(user_id),
                conversation_id=str(conversation_id),
                turn_id=str(row.id),
            )
        return _turn(row)

    def save_turn(self, workspace_id: UUID, conversation_id: UUID, turn: Turn) -> None:
        verdicts = {
            str(key): {"verdict": j.verdict.value, "reason": j.reason, "by_model": j.by_model}
            for key, j in turn.verdicts.items()
        }
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE reporter_turns SET status = :status, operation = :operation,"
                    " state = CAST(:state AS jsonb), concepts = CAST(:concepts AS jsonb),"
                    " candidates = CAST(:candidates AS jsonb), fact = CAST(:fact AS jsonb),"
                    " verdicts = CAST(:verdicts AS jsonb), error = :error, model = :model,"
                    " attempts = CAST(:attempts AS jsonb), finished_at = :finished"
                    f" WHERE id = :id AND conversation_id = :conversation AND {here()}"
                ),
                {
                    "id": turn.id,
                    "conversation": conversation_id,
                    "status": turn.status,
                    "operation": None if turn.operation is None else turn.operation.value,
                    "state": _state_json(turn.state),
                    "concepts": _concepts_json(turn.concepts, turn.term_counts),
                    "candidates": _candidates_json(turn.candidates),
                    "fact": _fact_json(turn.fact),
                    "verdicts": json.dumps(verdicts),
                    "error": turn.error,
                    "model": turn.model,
                    "attempts": json.dumps(turn.attempts),
                    "finished": turn.finished_at,
                },
            )

    def articles(self, workspace_id: UUID, item_ids: list[UUID]) -> list[Article]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = {
                row.id: row
                for row in connection.execute(
                    sa.text(
                        "SELECT i.id, i.title,"
                        " coalesce(i.text, i.feed_content, i.summary, '') AS body,"
                        " coalesce(s.name, i.declared_origin, '') AS publisher"
                        " FROM source_items AS i LEFT JOIN sources AS s ON s.id = i.source_id"
                        f" WHERE i.id = ANY(:ids) AND {here('i')}"
                    ),
                    {"ids": item_ids},
                ).all()
            }
        return [
            Article(
                str(item_id),
                rows[item_id].publisher,
                f"{rows[item_id].title}. {rows[item_id].body}",
            )
            for item_id in item_ids
            if item_id in rows
        ]
