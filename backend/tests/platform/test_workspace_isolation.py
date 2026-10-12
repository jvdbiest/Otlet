# SPDX-License-Identifier: AGPL-3.0-or-later
"""Forced row-level security with the session factory (S1.3, M-12): without a workspace
context, a query returns zero rows; with one, only that workspace's rows."""

import uuid
from collections.abc import Iterator

import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.platform import database as db

pytestmark = requires_database

WORKSPACE_A = uuid.UUID("018f0000-0000-7000-8000-00000000000a")
WORKSPACE_B = uuid.UUID("018f0000-0000-7000-8000-00000000000b")
# Empty once a transaction-local setting has been reset in the session: NULLIF keeps the cast
# from failing, and NULL lets no row through.
CURRENT_WORKSPACE = "NULLIF(current_setting('app.workspace_id', true), '')::uuid"


@pytest.fixture
def notes(migrated: TestDatabase) -> Iterator[TestDatabase]:
    """A workspace-scoped table owned by the schema owner, with the policy of the product."""
    with db.create_engine(migrated.migrator_url).begin() as connection:
        connection.execute(sa.text("SET LOCAL ROLE otlet_owner"))
        connection.execute(
            sa.text("CREATE TABLE isolation_notes (workspace_id uuid NOT NULL, body text NOT NULL)")
        )
        connection.execute(sa.text("ALTER TABLE isolation_notes ENABLE ROW LEVEL SECURITY"))
        connection.execute(sa.text("ALTER TABLE isolation_notes FORCE ROW LEVEL SECURITY"))
        connection.execute(
            sa.text(
                "CREATE POLICY workspace_isolation ON isolation_notes"
                f" USING (workspace_id = {CURRENT_WORKSPACE})"
                f" WITH CHECK (workspace_id = {CURRENT_WORKSPACE})"
            )
        )
        connection.execute(
            sa.text("GRANT SELECT, INSERT, UPDATE, DELETE ON isolation_notes TO otlet_app")
        )
    app = db.create_engine(migrated.app_url)
    for workspace in (WORKSPACE_A, WORKSPACE_B):
        with db.workspace_transaction(app, workspace) as connection:
            connection.execute(
                sa.text("INSERT INTO isolation_notes VALUES (:w, 'note')"), {"w": workspace}
            )
    yield migrated
    with db.create_engine(migrated.migrator_url).begin() as connection:
        connection.execute(sa.text("SET LOCAL ROLE otlet_owner"))
        connection.execute(sa.text("DROP TABLE isolation_notes"))


def test_query_without_context_returns_zero_rows(notes: TestDatabase) -> None:
    with db.create_engine(notes.app_url).connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM isolation_notes")).scalar() == 0


def test_context_shows_only_its_workspace(notes: TestDatabase) -> None:
    with db.workspace_transaction(db.create_engine(notes.app_url), WORKSPACE_A) as connection:
        rows = connection.execute(sa.text("SELECT workspace_id FROM isolation_notes")).scalars()
        assert list(rows) == [WORKSPACE_A]


def test_context_does_not_survive_the_transaction(notes: TestDatabase) -> None:
    engine = db.create_engine(notes.app_url, pool_size=1, max_overflow=0)
    with db.workspace_transaction(engine, WORKSPACE_A):
        pass
    # Same pooled connection, new transaction: the setting is gone.
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM isolation_notes")).scalar() == 0


def test_cannot_write_into_another_workspace(notes: TestDatabase) -> None:
    with pytest.raises(sa.exc.ProgrammingError, match="row-level security"):
        with db.workspace_transaction(db.create_engine(notes.app_url), WORKSPACE_A) as connection:
            connection.execute(
                sa.text("INSERT INTO isolation_notes VALUES (:w, 'intrusion')"),
                {"w": WORKSPACE_B},
            )
