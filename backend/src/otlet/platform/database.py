# SPDX-License-Identifier: AGPL-3.0-or-later
"""Database engine, schema state, and the session factory that carries the workspace context
(ARCHITECTURE §8.1, TECH_CHOICES §5.3 and §7.4)."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import sqlalchemy as sa

# Fail fast in health checks instead of hanging on an unreachable server.
CONNECT_TIMEOUT_SECONDS = 3

# Read by the row-level security policies (otlet.platform.rls): the current workspace for the
# business tables, the current user for the instance-level account tables.
WORKSPACE_SETTING = "app.workspace_id"
USER_SETTING = "app.user_id"


def create_engine(url: str, **options: object) -> sa.Engine:
    return sa.create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        **options,
    )


def schema_revision(engine: sa.Engine) -> str | None:
    """Current Alembic revision, or None when the schema has not been created yet."""
    with engine.connect() as connection:
        if not sa.inspect(connection).has_table("alembic_version"):
            return None
        return connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()


@contextmanager
def scoped_transaction(
    engine: sa.Engine, *, workspace_id: UUID | None = None, user_id: UUID | None = None
) -> Iterator[sa.Connection]:
    """A transaction in which row-level security lets through the rows of the given workspace
    and user only.

    The settings are local to the transaction (`set_config(…, true)`, the bindable form of
    `SET LOCAL`): they disappear at commit or rollback, so a pooled connection never carries a
    context into the next request or task. A context left out is empty, and the policies that
    read it let no row through. Both are set in a single round trip.
    """
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "SELECT set_config(:workspace_name, :workspace, true),"
                " set_config(:user_name, :user, true)"
            ),
            {
                "workspace_name": WORKSPACE_SETTING,
                "workspace": "" if workspace_id is None else str(workspace_id),
                "user_name": USER_SETTING,
                "user": "" if user_id is None else str(user_id),
            },
        )
        yield connection


@contextmanager
def workspace_transaction(engine: sa.Engine, workspace_id: UUID) -> Iterator[sa.Connection]:
    """A transaction limited to the rows of one workspace (see scoped_transaction)."""
    with scoped_transaction(engine, workspace_id=workspace_id) as connection:
        yield connection
