# SPDX-License-Identifier: AGPL-3.0-or-later
"""The writing charter of each user, on PostgreSQL, in the context of that user."""

from uuid import UUID

import sqlalchemy as sa

from otlet.platform.database import scoped_transaction


class PostgresCharters:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def get(self, user_id: UUID) -> str | None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            found: str | None = connection.execute(
                sa.text("SELECT charter FROM writing_charters WHERE user_id = :user"),
                {"user": user_id},
            ).scalar()
        return found

    def set(self, user_id: UUID, charter: str | None) -> None:
        """Keeps the user's charter; None goes back to the default one."""
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            if charter is None:
                connection.execute(
                    sa.text("DELETE FROM writing_charters WHERE user_id = :user"),
                    {"user": user_id},
                )
                return
            connection.execute(
                sa.text(
                    "INSERT INTO writing_charters (user_id, charter) VALUES (:user, :charter)"
                    " ON CONFLICT (user_id) DO UPDATE SET charter = EXCLUDED.charter,"
                    " updated_at = now()"
                ),
                {"user": user_id, "charter": charter},
            )
