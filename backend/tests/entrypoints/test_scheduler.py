# SPDX-License-Identifier: AGPL-3.0-or-later
"""The scheduler enqueues the collections that are due, once each (U01, ADR-0030)."""

from pathlib import Path

import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.collection.adapters.postgres import PostgresCollectionStore
from otlet.entrypoints.scheduler.main import Scheduler
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.platform.config import Settings
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces

pytestmark = requires_database


def collect_jobs(database: TestDatabase) -> int:
    with db.create_engine(database.admin_url).connect() as connection:
        return int(
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM procrastinate_jobs"
                    " WHERE task_name = 'collection.collect_source'"
                )
            ).scalar_one()
        )


def test_the_leader_enqueues_due_collections_once(migrated: TestDatabase, tmp_path: Path) -> None:
    engine = db.create_engine(migrated.app_url)
    user = Authentication(PostgresIdentityStore(engine), Argon2Hasher()).create_user(
        "joel", "joel@example.org", "une phrase de passe assez longue"
    )
    workspace = Workspaces(PostgresWorkspaceStore(engine)).create(user, "Veille").id
    store = PostgresCollectionStore(engine, lambda connection, name, **kwargs: 0)
    store.add_source(
        workspace,
        name="Journal",
        url="https://journal.example.org/feed.xml",
        feed_url="https://journal.example.org/feed.xml",
        site_url=None,
        interval_minutes=60,
    )
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=migrated.app_url)
    leader, follower = Scheduler(settings), Scheduler(settings)
    try:
        leader.step()
        follower.step()
        assert collect_jobs(migrated) == 1
    finally:
        leader.close()
        follower.close()
