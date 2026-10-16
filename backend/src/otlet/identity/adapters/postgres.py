# SPDX-License-Identifier: AGPL-3.0-or-later
"""The identity store on PostgreSQL (ADR-0028, ADR-0029).

Every query runs under row-level security: the account tables in the user context, and the
lookups that precede any context (sign-in, cookie, throttle) through the schema owner's
functions only.
"""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.identity.application.authentication import Identity, User
from otlet.identity.domain.model import PASSWORD_KIND, Session
from otlet.platform.database import scoped_transaction


class PostgresIdentityStore:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def find_identity(self, kind: str, subject: str) -> Identity | None:
        with self._engine.begin() as connection:
            row = connection.execute(
                sa.text(
                    "SELECT identity_id, user_id, credential, disabled"
                    " FROM find_identity(:kind, '', :subject)"
                ),
                {"kind": kind, "subject": subject},
            ).one_or_none()
        return None if row is None else Identity(*row)

    def password_identity(self, user_id: UUID) -> Identity | None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            row = connection.execute(
                sa.text(
                    "SELECT i.id, i.user_id, i.credential, u.disabled_at IS NOT NULL"
                    " FROM user_identities AS i JOIN users AS u ON u.id = i.user_id"
                    " WHERE i.kind = :kind AND i.issuer = ''"
                ),
                {"kind": PASSWORD_KIND},
            ).one_or_none()
        return None if row is None else Identity(*row)

    def create_user(
        self, display_name: str, login: str, credential: str, is_instance_admin: bool
    ) -> UUID:
        user_id = uuid4()
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO users (id, display_name, is_instance_admin)"
                    " VALUES (:id, :name, :admin)"
                ),
                {"id": user_id, "name": display_name, "admin": is_instance_admin},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO user_identities (user_id, kind, subject, credential)"
                    " VALUES (:user, :kind, :subject, :credential)"
                ),
                {
                    "user": user_id,
                    "kind": PASSWORD_KIND,
                    "subject": login,
                    "credential": credential,
                },
            )
        return user_id

    def get_user(self, user_id: UUID) -> User:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            row = connection.execute(
                sa.text("SELECT id, display_name, is_instance_admin FROM users WHERE id = :id"),
                {"id": user_id},
            ).one()
        return User(*row)

    def mark_identity_used(self, identity: Identity, now: datetime) -> None:
        with scoped_transaction(self._engine, user_id=identity.user_id) as connection:
            connection.execute(
                sa.text("UPDATE user_identities SET last_used_at = :now WHERE id = :id"),
                {"now": now, "id": identity.id},
            )

    def replace_credential(self, identity: Identity, credential: str) -> None:
        with scoped_transaction(self._engine, user_id=identity.user_id) as connection:
            connection.execute(
                sa.text("UPDATE user_identities SET credential = :credential WHERE id = :id"),
                {"credential": credential, "id": identity.id},
            )

    def throttle_failures(self, key: str, window: timedelta) -> int:
        return self._throttle("SELECT auth_throttle_failures(:key, :window)", key, window)

    def throttle_record_failure(self, key: str, window: timedelta) -> int:
        return self._throttle("SELECT auth_throttle_record(:key, :window)", key, window)

    def throttle_clear(self, key: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(sa.text("SELECT auth_throttle_clear(:key)"), {"key": key})

    def _throttle(self, query: str, key: str, window: timedelta) -> int:
        with self._engine.begin() as connection:
            value = connection.execute(sa.text(query), {"key": key, "window": window})
            return int(value.scalar_one())

    def create_session(
        self, user_id: UUID, token_hash: bytes, now: datetime, user_agent: str | None
    ) -> Session:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO user_sessions (user_id, token_hash, created_at, last_seen_at,"
                    " reauthenticated_at, user_agent)"
                    " VALUES (:user, :hash, :now, :now, :now, :agent)"
                    " RETURNING id, user_id, created_at, last_seen_at, reauthenticated_at, false"
                ),
                {"user": user_id, "hash": token_hash, "now": now, "agent": user_agent},
            ).one()
        return Session(*row)

    def find_session(self, token_hash: bytes) -> Session | None:
        with self._engine.begin() as connection:
            row = connection.execute(
                sa.text(
                    "SELECT session_id, user_id, created_at, last_seen_at, reauthenticated_at,"
                    " disabled FROM find_session(:hash)"
                ),
                {"hash": token_hash},
            ).one_or_none()
        return None if row is None else Session(*row)

    def touch_session(self, session: Session, now: datetime) -> None:
        self._update_session(session, "last_seen_at", now)

    def mark_reauthenticated(self, session: Session, now: datetime) -> None:
        self._update_session(session, "reauthenticated_at", now)

    def _update_session(self, session: Session, column: str, now: datetime) -> None:
        with scoped_transaction(self._engine, user_id=session.user_id) as connection:
            connection.execute(
                sa.text(f"UPDATE user_sessions SET {column} = :now WHERE id = :id"),  # noqa: S608
                {"now": now, "id": session.id},
            )

    def delete_session(self, session: Session) -> None:
        with scoped_transaction(self._engine, user_id=session.user_id) as connection:
            connection.execute(
                sa.text("DELETE FROM user_sessions WHERE id = :id"), {"id": session.id}
            )

    def delete_other_sessions(self, session: Session) -> None:
        with scoped_transaction(self._engine, user_id=session.user_id) as connection:
            connection.execute(
                sa.text("DELETE FROM user_sessions WHERE id <> :id"), {"id": session.id}
            )
