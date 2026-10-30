# SPDX-License-Identifier: AGPL-3.0-or-later
"""The vectors of the items on PostgreSQL (pgvector), each written in its workspace."""

import itertools

import sqlalchemy as sa

from otlet.meaning.application.meaning import Pending
from otlet.platform.database import scoped_transaction, workspace_transaction


def literal(vector: list[float]) -> str:
    """A vector as pgvector reads it: « [0.1,0.2,…] »."""
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"


class PostgresMeaningStore:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def pending(self, limit: int) -> list[Pending]:
        with scoped_transaction(self._engine) as connection:
            rows = connection.execute(
                sa.text("SELECT workspace_id, item_id, title, summary FROM unmeant_items(:limit)"),
                {"limit": limit},
            ).all()
        return [Pending(r.workspace_id, r.item_id, r.title, r.summary) for r in rows]

    def save(self, vectors: list[tuple[Pending, list[float]]], model: str) -> None:
        by_workspace = itertools.groupby(
            sorted(vectors, key=lambda v: str(v[0].workspace_id)),
            key=lambda v: v[0].workspace_id,
        )
        for workspace_id, rows in by_workspace:
            with workspace_transaction(self._engine, workspace_id) as connection:
                connection.execute(
                    sa.text(
                        "UPDATE source_items SET meaning = CAST(:vector AS vector),"
                        " meaning_model = :model WHERE id = :id"
                    ),
                    [
                        {"id": pending.item_id, "vector": literal(vector), "model": model}
                        for pending, vector in rows
                    ],
                )
