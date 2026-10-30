# SPDX-License-Identifier: AGPL-3.0-or-later
"""The conversations of the Reporter on PostgreSQL, in the context of each workspace."""

import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.assistant.application.assistant import Candidate
from otlet.assistant.domain.qualify import Judged, Verdict
from otlet.assistant.domain.terms import Concept, Widened
from otlet.jobs.application.registry import Enqueue, no_queue
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here
from otlet.reporter.application.reporter import ANSWER_TURN, Conversation, RunningTurn, Turn
from otlet.reporter.domain.facts import Agreement, Article, Compared, Fact, FactLine
from otlet.reporter.domain.questions import PROMPT_VERSION, Operation, State
from otlet.reporter.domain.reading import Answer, Coverage, Reading, Round
from otlet.reporter.domain.reconstitution import (
    Confidence,
    Facet,
    RebuiltLine,
    Reconstitution,
    Sentence,
)

TURN_COLUMNS = (
    "id, position, question, status, operation, state, concepts, candidates, fact, verdicts,"
    " reading, reconstitution, error, model, prompt_version, attempts, created_at, finished_at"
)
REQUESTED = json.dumps({"requested": True})


def _concept(data: dict[str, Any]) -> Concept:
    return Concept(data["name"], tuple(data["terms"]))


def _day(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def _state_json(state: State) -> str:
    return json.dumps(
        {
            "concepts": [{"name": c.name, "terms": list(c.terms)} for c in state.concepts],
            "language": state.language,
            "days": state.days,
            "meaning": list(state.meaning),
            "subject": state.subject,
            "excluded": list(state.excluded),
            "date_from": None if state.date_from is None else state.date_from.isoformat(),
            "date_to": None if state.date_to is None else state.date_to.isoformat(),
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


def _reading_json(reading: Reading | None) -> str | None:
    if reading is None:
        return None
    return json.dumps(
        {
            "requested": reading.requested,
            "rounds": [
                {
                    "concepts": [{"name": c.name, "terms": list(c.terms)} for c in r.concepts],
                    "read": list(r.read),
                    "found": r.found,
                }
                for r in reading.rounds
            ],
            "answers": [
                {
                    "item_id": a.item_id,
                    "title": a.title,
                    "publisher": a.publisher,
                    "dated": a.dated,
                    "url": a.url,
                    "reason": a.reason,
                    "round": a.round,
                }
                for a in reading.answers
            ],
            "coverage": None if reading.coverage is None else reading.coverage.value,
            "missing": reading.missing,
            "errors": list(reading.errors),
        }
    )


def _reconstitution_json(rebuilt: Reconstitution | None) -> str | None:
    if rebuilt is None:
        return None
    data = asdict(rebuilt)
    data["confidence"] = None if rebuilt.confidence is None else rebuilt.confidence.value
    return json.dumps(data)


def _rebuilt_line(data: dict[str, Any]) -> RebuiltLine:
    return RebuiltLine(**{**data, "to_check": tuple(data.get("to_check", ()))})


def _read_sentences(rows: list[dict[str, Any]]) -> tuple[Sentence, ...]:
    return tuple(
        Sentence(s["text"], tuple(s["lines"]), s["deduction"], tuple(s["unsupported"]))
        for s in rows
    )


def _reconstitution(data: dict[str, Any] | None) -> Reconstitution | None:
    if data is None:
        return None
    level = data.get("confidence")
    return Reconstitution(
        requested=bool(data.get("requested")),
        form=data.get("form", ""),
        facets=tuple(Facet(**f) for f in data.get("facets", [])),
        lines=tuple(_rebuilt_line(line) for line in data.get("lines", [])),
        flagged=tuple(_rebuilt_line(line) for line in data.get("flagged", [])),
        answer=_read_sentences(data.get("answer", [])),
        sentences=_read_sentences(data.get("sentences", [])),
        confidence=None if level is None else Confidence(level),
        reasons=tuple(data.get("reasons", [])),
        found=data.get("found", 0),
        read=data.get("read", 0),
        dropped=data.get("dropped", 0),
        errors=tuple(data.get("errors", [])),
    )


def _reading(data: dict[str, Any] | None) -> Reading | None:
    if data is None:
        return None
    return Reading(
        requested=bool(data.get("requested")),
        rounds=tuple(
            Round(tuple(_concept(c) for c in r["concepts"]), tuple(r["read"]), r["found"])
            for r in data.get("rounds", [])
        ),
        answers=tuple(Answer(**a) for a in data.get("answers", [])),
        coverage=None if data.get("coverage") is None else Coverage(data["coverage"]),
        missing=data.get("missing", ""),
        errors=tuple(data.get("errors", [])),
    )


def _turn(row: sa.Row[Any]) -> Turn:
    return Turn(
        id=row.id,
        position=row.position,
        question=row.question,
        status=row.status,
        operation=None if row.operation is None else Operation(row.operation),
        state=State(
            tuple(_concept(c) for c in row.state.get("concepts", [])),
            row.state.get("language"),
            row.state.get("days"),
            tuple(row.state.get("meaning", ())),
            row.state.get("subject", 0),
            tuple(row.state.get("excluded", ())),
            _day(row.state.get("date_from")),
            _day(row.state.get("date_to")),
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
        reading=_reading(row.reading),
        reconstitution=_reconstitution(row.reconstitution),
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
        self,
        workspace_id: UUID,
        user_id: UUID,
        conversation_id: UUID,
        question: str,
        read: bool = False,
        dates: tuple[date | None, date | None] = (None, None),
    ) -> Turn:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO reporter_turns (id, workspace_id, conversation_id, position,"
                    " question, prompt_version, reading, state) SELECT :id, :workspace,"
                    " :conversation, coalesce(max(position), 0) + 1, :question, :version,"
                    " CAST(:reading AS jsonb), CAST(:state AS jsonb) FROM reporter_turns"
                    f" WHERE conversation_id = :conversation AND {here()}"
                    f" RETURNING {TURN_COLUMNS}"
                ),
                {
                    "id": uuid4(),
                    "workspace": workspace_id,
                    "conversation": conversation_id,
                    "question": question,
                    "version": PROMPT_VERSION,
                    "reading": REQUESTED if read else None,
                    "state": _state_json(State(date_from=dates[0], date_to=dates[1])),
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

    def read_further(
        self, workspace_id: UUID, user_id: UUID, conversation_id: UUID, turn_id: UUID
    ) -> Turn:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "UPDATE reporter_turns SET status = 'pending', finished_at = NULL"
                    f" WHERE id = :id AND conversation_id = :conversation AND {here()}"
                    f" RETURNING {TURN_COLUMNS}"
                ),
                {"id": turn_id, "conversation": conversation_id},
            ).one()
            self._enqueue(
                connection,
                ANSWER_TURN,
                workspace_id=str(workspace_id),
                user_id=str(user_id),
                conversation_id=str(conversation_id),
                turn_id=str(turn_id),
            )
        return _turn(row)

    def request_reconstitution(
        self, workspace_id: UUID, user_id: UUID, conversation_id: UUID, turn_id: UUID
    ) -> Turn:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "UPDATE reporter_turns SET status = 'pending', finished_at = NULL,"
                    " reconstitution = CAST(:requested AS jsonb)"
                    f" WHERE id = :id AND conversation_id = :conversation AND {here()}"
                    f" RETURNING {TURN_COLUMNS}"
                ),
                {"id": turn_id, "conversation": conversation_id, "requested": REQUESTED},
            ).one()
            self._enqueue(
                connection,
                ANSWER_TURN,
                workspace_id=str(workspace_id),
                user_id=str(user_id),
                conversation_id=str(conversation_id),
                turn_id=str(turn_id),
            )
        return _turn(row)

    def request_reading(
        self, workspace_id: UUID, user_id: UUID, conversation_id: UUID, turn_id: UUID
    ) -> Turn:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "UPDATE reporter_turns SET status = 'pending', finished_at = NULL,"
                    " reading = CAST(:reading AS jsonb)"
                    f" WHERE id = :id AND conversation_id = :conversation AND {here()}"
                    f" RETURNING {TURN_COLUMNS}"
                ),
                {"id": turn_id, "conversation": conversation_id, "reading": REQUESTED},
            ).one()
            self._enqueue(
                connection,
                ANSWER_TURN,
                workspace_id=str(workspace_id),
                user_id=str(user_id),
                conversation_id=str(conversation_id),
                turn_id=str(turn_id),
            )
        return _turn(row)

    def delete_conversations(
        self, workspace_id: UUID, user_id: UUID, conversation_ids: list[UUID]
    ) -> int:
        with workspace_transaction(self._engine, workspace_id) as connection:
            return connection.execute(
                sa.text(
                    "DELETE FROM reporter_conversations"
                    f" WHERE id = ANY(:ids) AND created_by = :user AND {here()}"
                ),
                {"ids": conversation_ids, "user": user_id},
            ).rowcount

    def is_pending(self, workspace_id: UUID, turn_id: UUID) -> bool:
        """Whether a question is still being answered: what a call in progress looks at."""
        with workspace_transaction(self._engine, workspace_id) as connection:
            status = connection.execute(
                sa.text(f"SELECT status FROM reporter_turns WHERE id = :id AND {here()}"),
                {"id": turn_id},
            ).scalar()
        return status == "pending"

    def running_turns(self, workspace_id: UUID, user_id: UUID) -> list[RunningTurn]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT t.conversation_id, t.id, t.question, t.created_at FROM reporter_turns t"
                    " JOIN reporter_conversations c ON c.id = t.conversation_id"
                    f" WHERE t.status = 'pending' AND c.created_by = :user AND {here('t')}"
                    " ORDER BY t.created_at"
                ),
                {"user": user_id},
            ).all()
        return [RunningTurn(r.conversation_id, r.id, r.question, r.created_at) for r in rows]

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
                    " verdicts = CAST(:verdicts AS jsonb), reading = CAST(:reading AS jsonb),"
                    " reconstitution = CAST(:reconstitution AS jsonb),"
                    " error = :error, model = :model,"
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
                    "reading": _reading_json(turn.reading),
                    "reconstitution": _reconstitution_json(turn.reconstitution),
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
