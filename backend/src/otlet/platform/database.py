# SPDX-License-Identifier: AGPL-3.0-or-later
"""Database engine and schema state. The per-workspace session factory (SET LOCAL, RLS) comes
with S1."""

import sqlalchemy as sa

# Fail fast in health checks instead of hanging on an unreachable server.
CONNECT_TIMEOUT_SECONDS = 3


def create_engine(url: str) -> sa.Engine:
    return sa.create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def schema_revision(engine: sa.Engine) -> str | None:
    """Current Alembic revision, or None when the schema has not been created yet."""
    with engine.connect() as connection:
        if not sa.inspect(connection).has_table("alembic_version"):
            return None
        return connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
