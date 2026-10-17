# SPDX-License-Identifier: AGPL-3.0-or-later
"""The journal of AI calls on PostgreSQL, under row-level security (user scope)."""

from typing import Any
from uuid import UUID

import sqlalchemy as sa

from otlet.ai.application.gateway import Attempt
from otlet.platform.database import scoped_transaction


class PostgresCallJournal:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def record(self, user_id: UUID, attempt: Attempt) -> None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO ai_calls (user_id, usage, provider_id, provider_kind, model,"
                    " result, detail, tokens_in, tokens_out, cost, seconds, at) VALUES (:user,"
                    " :usage, :provider, :kind, :model, :result, :detail, :tokens_in,"
                    " :tokens_out, :cost, :seconds, :at)"
                ),
                {
                    "user": user_id,
                    "usage": attempt.usage,
                    "provider": attempt.provider_id,
                    "kind": attempt.provider_kind,
                    "model": attempt.model,
                    "result": attempt.result,
                    "detail": attempt.detail,
                    "tokens_in": attempt.tokens_in,
                    "tokens_out": attempt.tokens_out,
                    "cost": attempt.cost,
                    "seconds": attempt.seconds,
                    "at": attempt.at,
                },
            )

    def recent(self, user_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            rows = (
                connection.execute(
                    sa.text(
                        "SELECT usage, provider_kind, model, result, detail, tokens_in, tokens_out,"
                        " cost, seconds, at FROM ai_calls WHERE user_id = :user"
                        " ORDER BY at DESC, id DESC LIMIT :limit"
                    ),
                    {"user": user_id, "limit": limit},
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]
