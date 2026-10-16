# SPDX-License-Identifier: AGPL-3.0-or-later
"""Migration 0008 removes what a superuser wrote across workspaces before M-12 reached the
Compose stack, and hands the items back to the watch."""

import uuid
from pathlib import Path

import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.platform import database as db
from otlet.platform import migrations
from otlet.platform.config import Settings

pytestmark = requires_database


def test_cross_workspace_rows_are_repaired(migrated: TestDatabase, tmp_path: Path) -> None:
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=migrated.migrator_url)
    migrations.downgrade(settings, "0007")
    a, b = uuid.uuid4(), uuid.uuid4()
    topic, item, source = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with db.create_engine(migrated.admin_url).begin() as connection:
        run = connection.execute
        run(
            sa.text("INSERT INTO workspaces (id, name) VALUES (:a, 'A'), (:b, 'B')"),
            {"a": a, "b": b},
        )
        run(
            sa.text(
                "INSERT INTO sources (id, workspace_id, name, url, feed_url, interval_minutes)"
                " VALUES (:s, :a, 'S', 'https://x.org/f', 'https://x.org/f', 60)"
            ),
            {"s": source, "a": a},
        )
        run(
            sa.text(
                "INSERT INTO source_items (id, workspace_id, source_id, origin, guid, title,"
                " text_status, watched_at) VALUES (:i, :a, :s, 'feed', 'g', 'T', 'full_text',"
                " now())"
            ),
            {"i": item, "a": a, "s": source},
        )
        run(
            sa.text(
                "INSERT INTO topics (id, workspace_id, name, keywords) VALUES (:t, :a, 'T', '{x}')"
            ),
            {"t": topic, "a": a},
        )
        # The wrong workspace, as the superuser wrote it.
        run(
            sa.text(
                "INSERT INTO topic_matches (workspace_id, topic_id, item_id, score, contributions)"
                " VALUES (:b, :t, :i, 3, '[]')"
            ),
            {"b": b, "t": topic, "i": item},
        )
    migrations.upgrade(settings)
    with db.create_engine(migrated.admin_url).connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM topic_matches")).scalar() == 0
        watched = connection.execute(
            sa.text("SELECT watched_at FROM source_items WHERE id = :i"), {"i": item}
        ).scalar()
        assert watched is None  # handed back to the watch
