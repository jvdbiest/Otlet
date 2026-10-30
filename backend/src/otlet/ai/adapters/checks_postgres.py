# SPDX-License-Identifier: AGPL-3.0-or-later
"""Checks of the AI profile on PostgreSQL, under row-level security (user scope)."""

import json
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from otlet.ai.application.checks import CHECK_PROFILE, Check
from otlet.jobs.application.registry import Enqueue
from otlet.platform.database import scoped_transaction

COLUMNS = "id, created_at, finished_at, result"


def _check(row: sa.Row[Any]) -> Check:
    return Check(row.id, row.created_at, row.finished_at, row.result)


class PostgresChecks:
    def __init__(self, engine: sa.Engine, enqueue: Enqueue) -> None:
        self._engine = engine
        self._enqueue = enqueue

    def create(self, user_id: UUID, check_id: UUID) -> Check:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            row = connection.execute(
                sa.text(
                    f"INSERT INTO ai_checks (id, user_id) VALUES (:id, :user) RETURNING {COLUMNS}"
                ),
                {"id": check_id, "user": user_id},
            ).one()
            self._enqueue(connection, CHECK_PROFILE, user_id=str(user_id), check_id=str(check_id))
        return _check(row)

    def get(self, user_id: UUID, check_id: UUID) -> Check | None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            row = connection.execute(
                sa.text(f"SELECT {COLUMNS} FROM ai_checks WHERE id = :id AND user_id = :user"),
                {"id": check_id, "user": user_id},
            ).one_or_none()
        return None if row is None else _check(row)

    def finish(self, user_id: UUID, check_id: UUID, result: dict[str, Any]) -> None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE ai_checks SET result = CAST(:result AS jsonb), finished_at = now()"
                    " WHERE id = :id AND user_id = :user AND finished_at IS NULL"
                ),
                {"id": check_id, "user": user_id, "result": json.dumps(result)},
            )

    def running(self, user_id: UUID) -> list[Check]:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {COLUMNS} FROM ai_checks"
                    " WHERE user_id = :user AND finished_at IS NULL ORDER BY created_at"
                ),
                {"user": user_id},
            ).all()
        return [_check(row) for row in rows]
