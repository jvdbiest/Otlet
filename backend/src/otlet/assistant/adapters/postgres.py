# SPDX-License-Identifier: AGPL-3.0-or-later
"""The glossary, the search by concepts and the dossiers of the Assistant de veille on
PostgreSQL, in the context of each workspace."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.assistant.application.assistant import Candidate, StoredEntry
from otlet.assistant.application.dossiers import QUALIFY_DOSSIER, Dossier, RunningDossier
from otlet.assistant.domain.qualify import PROMPT_VERSION, Judged, Verdict
from otlet.assistant.domain.terms import Concept, GlossaryEntry, Widened, websearch
from otlet.jobs.application.registry import Enqueue, no_queue
from otlet.meaning.adapters.postgres import literal
from otlet.meaning.domain.meaning import MODEL
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here

# The candidates of one concept: the most recent items holding one of its terms, in any
# language of the index (search_candidates, ADR-0033, ADR-0034).
CONCEPT_WINDOW = 5000
SUMMARY_CHARS = 400


def _entry(row: sa.Row[Any]) -> StoredEntry:
    return StoredEntry(row.id, GlossaryEntry(tuple(row.terms)), row.updated_at)


DOSSIER_COLUMNS = (
    "id, subject, angle, days, status, concepts, candidates, verdicts, error, model,"
    " prompt_version, attempts, created_at, finished_at"
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


def _dossier(row: sa.Row[Any]) -> Dossier:
    return Dossier(
        id=row.id,
        subject=row.subject,
        angle=row.angle,
        days=row.days,
        status=row.status,
        concepts=[
            Widened(
                Concept(c["name"], tuple(c["terms"])),
                tuple(c["added"]),
                tuple(c.get("general", ())),
            )
            for c in row.concepts
        ],
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
        term_counts={term: n for c in row.concepts for term, n in c.get("counts", {}).items()},
    )


class PostgresAssistantStore:
    def __init__(self, engine: sa.Engine, enqueue: Enqueue = no_queue) -> None:
        self._engine = engine
        self._enqueue = enqueue

    # Glossary ---------------------------------------------------------------------------------

    def glossary(self, workspace_id: UUID) -> list[StoredEntry]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT id, terms, updated_at FROM glossary_entries"
                    f" WHERE {here()} ORDER BY lower(terms[1]), id"
                )
            ).all()
        return [_entry(row) for row in rows]

    def add_entry(self, workspace_id: UUID, user_id: UUID, terms: tuple[str, ...]) -> StoredEntry:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO glossary_entries (id, workspace_id, terms, created_by)"
                    " VALUES (:id, :workspace, :terms, :user) RETURNING id, terms, updated_at"
                ),
                {"id": uuid4(), "workspace": workspace_id, "terms": list(terms), "user": user_id},
            ).one()
        return _entry(row)

    def update_entry(
        self, workspace_id: UUID, entry_id: UUID, terms: tuple[str, ...]
    ) -> StoredEntry | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "UPDATE glossary_entries SET terms = :terms, updated_at = now()"
                    f" WHERE id = :id AND {here()} RETURNING id, terms, updated_at"
                ),
                {"id": entry_id, "terms": list(terms)},
            ).one_or_none()
        return None if row is None else _entry(row)

    def delete_entry(self, workspace_id: UUID, entry_id: UUID) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            found = connection.execute(
                sa.text(f"DELETE FROM glossary_entries WHERE id = :id AND {here()} RETURNING id"),
                {"id": entry_id},
            ).one_or_none()
        return found is not None

    # Search by concepts ----------------------------------------------------------------------

    def candidates(
        self,
        workspace_id: UUID,
        concepts: list[Widened],
        since: datetime | None,
        limit: int,
    ) -> list[Candidate]:
        """The items holding a term of every concept, the best ranked first: no model. A term
        of several words holds when the item has all its words, in any order: as an exact
        phrase, « Région de Bruxelles-Capitale » found nothing (Joël, 2026-10-25)."""
        queries: dict[str, str] = {}
        groups = []
        for n, concept in enumerate(concepts):
            keys = []
            for m, term in enumerate(concept.terms):
                key = f"t{n}_{m}"
                queries[key] = websearch(term)
                keys.append(key)
            groups.append(
                "("
                + " UNION ".join(
                    f"SELECT id FROM search_candidates(:{key}, {CONCEPT_WINDOW})" for key in keys
                )
                + ")"
            )
        found = " INTERSECT ".join(groups)
        rank = " + ".join(
            f"ts_rank(i.search, websearch_to_tsquery(i.search_config, :{key}))" for key in queries
        )
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"WITH found AS ({found})"  # noqa: S608 (constant fragments, bound values)
                    " SELECT i.id, i.title, left(coalesce(i.summary, ''), :chars) AS summary,"
                    " i.url, i.language, coalesce(s.name, i.declared_origin) AS publisher,"
                    " coalesce(i.published_at, i.collected_at) AS dated,"
                    f" ({rank}) AS rank"
                    " FROM found JOIN source_items AS i ON i.id = found.id"
                    " LEFT JOIN sources AS s ON s.id = i.source_id"
                    f" WHERE {here('i')}"
                    " AND (CAST(:since AS timestamptz) IS NULL"
                    " OR coalesce(i.published_at, i.collected_at) >= :since)"
                    " ORDER BY rank DESC, dated DESC, i.id LIMIT :limit"
                ),
                {**queries, "chars": SUMMARY_CHARS, "since": since, "limit": limit},
            ).all()
        return [
            Candidate(
                id=row.id,
                title=row.title,
                summary=row.summary,
                url=row.url,
                language=row.language,
                publisher=row.publisher,
                dated=row.dated,
            )
            for row in rows
        ]

    def near(
        self,
        workspace_id: UUID,
        meaning: tuple[float, ...],
        since: datetime | None,
        limit: int,
        floor: float,
    ) -> list[Candidate]:
        """The items closest in meaning (ADR-0045). The index is read on, past the items of the
        other workspaces that row-level security hides, until `limit` are found (iterative scan
        of pgvector); only vectors of the model of the question compare."""
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(sa.text("SET LOCAL hnsw.iterative_scan = strict_order"))
            connection.execute(sa.text("SET LOCAL hnsw.ef_search = 100"))
            rows = connection.execute(
                sa.text(
                    "SELECT i.id, i.title, left(coalesce(i.summary, ''), :chars) AS summary,"
                    " i.url, i.language, coalesce(s.name, i.declared_origin) AS publisher,"
                    " coalesce(i.published_at, i.collected_at) AS dated,"
                    " 1 - (i.meaning <=> CAST(:meaning AS vector)) AS closeness"
                    " FROM source_items AS i LEFT JOIN sources AS s ON s.id = i.source_id"
                    f" WHERE {here('i')} AND i.duplicate_of IS NULL"
                    " AND i.meaning IS NOT NULL AND i.meaning_model = :model"
                    " AND (CAST(:since AS timestamptz) IS NULL"
                    " OR coalesce(i.published_at, i.collected_at) >= :since)"
                    " ORDER BY i.meaning <=> CAST(:meaning AS vector) LIMIT :limit"
                ),
                {
                    "chars": SUMMARY_CHARS,
                    "meaning": literal(list(meaning)),
                    "model": MODEL,
                    "since": since,
                    "limit": limit,
                },
            ).all()
        return [
            Candidate(
                id=row.id,
                title=row.title,
                summary=row.summary,
                url=row.url,
                language=row.language,
                publisher=row.publisher,
                dated=row.dated,
            )
            for row in rows
            if row.closeness >= floor
        ]

    def term_counts(
        self, workspace_id: UUID, terms: list[str], since: datetime | None
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        with workspace_transaction(self._engine, workspace_id) as connection:
            for term in dict.fromkeys(terms):
                counts[term] = connection.execute(
                    sa.text(
                        f"SELECT count(*) FROM search_candidates(:q, {CONCEPT_WINDOW}) AS c"
                        " WHERE CAST(:since AS timestamptz) IS NULL OR c.sort_date >= :since"
                    ),
                    {"q": websearch(term), "since": since},
                ).scalar_one()
        return counts

    def total_items(self, workspace_id: UUID, since: datetime | None) -> int:
        with workspace_transaction(self._engine, workspace_id) as connection:
            return int(
                connection.execute(
                    sa.text(
                        "SELECT count(*) FROM source_items AS i"
                        f" WHERE {here('i')} AND i.duplicate_of IS NULL"
                        " AND (CAST(:since AS timestamptz) IS NULL"
                        " OR coalesce(i.published_at, i.collected_at) >= :since)"
                    ),
                    {"since": since},
                ).scalar_one()
            )

    # Dossiers ---------------------------------------------------------------------------------

    def start_dossier(
        self,
        workspace_id: UUID,
        user_id: UUID,
        subject: str,
        angle: str,
        days: int | None,
        concepts: list[Concept],
    ) -> Dossier:
        requested = json.dumps([{"name": c.name, "terms": list(c.terms)} for c in concepts])
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO assistant_dossiers (id, workspace_id, created_by, subject, angle,"
                    " days, requested, prompt_version) VALUES (:id, :workspace, :user, :subject,"
                    " :angle, :days, CAST(:requested AS jsonb), :version)"
                    f" RETURNING {DOSSIER_COLUMNS}"
                ),
                {
                    "id": uuid4(),
                    "workspace": workspace_id,
                    "user": user_id,
                    "subject": subject,
                    "angle": angle,
                    "days": days,
                    "requested": requested,
                    "version": PROMPT_VERSION,
                },
            ).one()
            self._enqueue(
                connection,
                QUALIFY_DOSSIER,
                workspace_id=str(workspace_id),
                user_id=str(user_id),
                dossier_id=str(row.id),
            )
        return _dossier(row)

    def dossier(self, workspace_id: UUID, dossier_id: UUID) -> Dossier | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT {DOSSIER_COLUMNS} FROM assistant_dossiers WHERE id = :id AND {here()}"
                ),
                {"id": dossier_id},
            ).one_or_none()
        return None if row is None else _dossier(row)

    def dossiers(self, workspace_id: UUID, user_id: UUID, limit: int) -> list[Dossier]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {DOSSIER_COLUMNS} FROM assistant_dossiers"
                    f" WHERE created_by = :user AND {here()} ORDER BY created_at DESC LIMIT :limit"
                ),
                {"user": user_id, "limit": limit},
            ).all()
        return [_dossier(row) for row in rows]

    def requested_concepts(self, workspace_id: UUID, dossier_id: UUID) -> list[Concept]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            requested = connection.execute(
                sa.text(f"SELECT requested FROM assistant_dossiers WHERE id = :id AND {here()}"),
                {"id": dossier_id},
            ).scalar_one()
        return [Concept(c["name"], tuple(c["terms"])) for c in requested]

    def is_over(self, workspace_id: UUID, dossier_id: UUID) -> bool:
        """Whether a dossier is done, or cancelled: what a call in progress looks at."""
        with workspace_transaction(self._engine, workspace_id) as connection:
            status = connection.execute(
                sa.text(f"SELECT status FROM assistant_dossiers WHERE id = :id AND {here()}"),
                {"id": dossier_id},
            ).scalar()
        return status is None or status == "done"

    def running_dossiers(self, workspace_id: UUID, user_id: UUID) -> list[RunningDossier]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT id, subject, created_at FROM assistant_dossiers"
                    f" WHERE status <> 'done' AND created_by = :user AND {here()}"
                    " ORDER BY created_at"
                ),
                {"user": user_id},
            ).all()
        return [RunningDossier(r.id, r.subject, r.created_at) for r in rows]

    def save_dossier(self, workspace_id: UUID, dossier: Dossier, finished: bool) -> None:
        verdicts = {
            str(key): {"verdict": j.verdict.value, "reason": j.reason, "by_model": j.by_model}
            for key, j in dossier.verdicts.items()
        }
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE assistant_dossiers SET status = :status,"
                    " concepts = CAST(:concepts AS jsonb),"
                    " candidates = CAST(:candidates AS jsonb),"
                    " verdicts = CAST(:verdicts AS jsonb), error = :error, model = :model,"
                    " attempts = CAST(:attempts AS jsonb),"
                    " finished_at = CASE WHEN :finished THEN now() ELSE finished_at END"
                    f" WHERE id = :id AND {here()}"
                ),
                {
                    "id": dossier.id,
                    "status": dossier.status,
                    "concepts": _concepts_json(dossier.concepts, dossier.term_counts),
                    "candidates": _candidates_json(dossier.candidates),
                    "verdicts": json.dumps(verdicts),
                    "error": dossier.error,
                    "model": dossier.model,
                    "attempts": json.dumps(dossier.attempts),
                    "finished": finished,
                },
            )
