# SPDX-License-Identifier: AGPL-3.0-or-later
"""The glossary and the search by concepts on PostgreSQL, in the context of each workspace."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.assistant.application.assistant import Candidate, StoredEntry
from otlet.assistant.domain.terms import GlossaryEntry, Widened, websearch
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here

# The candidates of one concept: the most recent items holding one of its terms, in any
# language of the index (search_candidates, ADR-0033, ADR-0034).
CONCEPT_WINDOW = 5000
SUMMARY_CHARS = 400


def _entry(row: sa.Row[Any]) -> StoredEntry:
    return StoredEntry(row.id, GlossaryEntry(tuple(row.terms)), row.updated_at)


class PostgresAssistantStore:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

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
        """The items holding a term of every concept, the best ranked first: no model."""
        queries = {f"q{n}": websearch(c.terms) for n, c in enumerate(concepts)}
        found = " INTERSECT ".join(
            f"SELECT id FROM search_candidates(:{key}, {CONCEPT_WINDOW})" for key in queries
        )
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
