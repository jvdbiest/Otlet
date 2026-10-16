# SPDX-License-Identifier: AGPL-3.0-or-later
"""A single active scheduler (ARCHITECTURE §12.5, TECH_CHOICES §9.4): a PostgreSQL advisory
lock held by a dedicated connection. Whoever holds it leads; a second scheduler waits and takes
over when the first one disappears, because PostgreSQL releases the lock with its connection."""

import logging

import sqlalchemy as sa

logger = logging.getLogger(__name__)

# Advisory lock keys of the application (one bigint each).
SCHEDULER_LOCK = 0x4F544C45_54534348  # "OTLETSCH"


class LeaderLock:
    def __init__(self, engine: sa.Engine, key: int = SCHEDULER_LOCK) -> None:
        self._engine = engine
        self._key = key
        self._connection: sa.Connection | None = None

    def hold(self) -> bool:
        """True while this process leads; tries to take the lead when it does not."""
        try:
            if self._connection is not None:
                # The lock lives as long as this connection: check that it still does.
                self._connection.execute(sa.text("SELECT 1"))
                return True
            connection = self._engine.connect()
            taken = connection.execute(
                sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": self._key}
            ).scalar_one()
            # Autocommit-like: the lock is session-level, the transaction can end.
            connection.commit()
            if not taken:
                connection.close()
                return False
            self._connection = connection
            logger.info("leading the scheduling")
            return True
        except sa.exc.SQLAlchemyError:
            logger.warning("lost the scheduling lead", exc_info=True)
            self.release()
            return False

    def release(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.invalidate()  # closing the session releases the lock
        except sa.exc.SQLAlchemyError:
            pass
        self._connection = None
