# SPDX-License-Identifier: AGPL-3.0-or-later
"""Database engine, schema state, and the session factory that carries the workspace context
(ARCHITECTURE §8.1, TECH_CHOICES §5.3 and §7.4)."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import sqlalchemy as sa

# Fail fast in health checks instead of hanging on an unreachable server.
CONNECT_TIMEOUT_SECONDS = 3

# Read by the row-level security policies: workspace_id = current_setting(…)::uuid.
WORKSPACE_SETTING = "app.workspace_id"


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
def workspace_transaction(engine: sa.Engine, workspace_id: UUID) -> Iterator[sa.Connection]:
    """A transaction in which row-level security lets through the rows of one workspace only.

    The setting is local to the transaction (`set_config(…, true)`, the bindable form of
    `SET LOCAL`): it disappears at commit or rollback, so a pooled connection never carries a
    workspace into the next request or task. Outside such a transaction, the setting is empty
    and the policies let no row through.
    """
    with engine.begin() as connection:
        connection.execute(
            sa.text("SELECT set_config(:name, :value, true)"),
            {"name": WORKSPACE_SETTING, "value": str(workspace_id)},
        )
        yield connection
