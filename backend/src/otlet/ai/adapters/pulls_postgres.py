# SPDX-License-Identifier: AGPL-3.0-or-later
"""Model installations on PostgreSQL, under row-level security (user scope)."""

from typing import Any
from uuid import UUID

import sqlalchemy as sa

from otlet.ai.application.models import PULL_MODEL, Pull
from otlet.jobs.application.registry import Enqueue
from otlet.platform.database import scoped_transaction

COLUMNS = "id, provider_id, model, status, step, completed, total, error, created_at, finished_at"


def _pull(row: sa.Row[Any]) -> Pull:
    return Pull(
        id=row.id,
        provider_id=row.provider_id,
        model=row.model,
        status=row.status,
        step=row.step,
        completed=row.completed,
        total=row.total,
        error=row.error,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


class PostgresPulls:
    def __init__(self, engine: sa.Engine, enqueue: Enqueue) -> None:
        self._engine = engine
        self._enqueue = enqueue

    def create(self, user_id: UUID, pull_id: UUID, provider_id: UUID, model: str) -> Pull:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO ai_pulls (id, user_id, provider_id, model)"
                    f" VALUES (:id, :user, :provider, :model) RETURNING {COLUMNS}"
                ),
                {"id": pull_id, "user": user_id, "provider": provider_id, "model": model},
            ).one()
            self._enqueue(connection, PULL_MODEL, user_id=str(user_id), pull_id=str(pull_id))
        return _pull(row)

    def get(self, user_id: UUID, pull_id: UUID) -> Pull | None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            row = connection.execute(
                sa.text(f"SELECT {COLUMNS} FROM ai_pulls WHERE id = :id AND user_id = :user"),
                {"id": pull_id, "user": user_id},
            ).one_or_none()
        return None if row is None else _pull(row)

    def progress(self, user_id: UUID, pull_id: UUID, step: str, completed: int, total: int) -> None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE ai_pulls SET step = :step, completed = :completed, total = :total,"
                    " updated_at = now() WHERE id = :id AND user_id = :user"
                ),
                {
                    "id": pull_id,
                    "user": user_id,
                    "step": step[:200],
                    "completed": completed,
                    "total": total,
                },
            )

    def finish(self, user_id: UUID, pull_id: UUID, error: str | None) -> None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE ai_pulls SET status = :status, error = :error, updated_at = now(),"
                    " finished_at = now() WHERE id = :id AND user_id = :user"
                ),
                {
                    "id": pull_id,
                    "user": user_id,
                    "status": "done" if error is None else "failed",
                    "error": error,
                },
            )
