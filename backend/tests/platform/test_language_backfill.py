# SPDX-License-Identifier: AGPL-3.0-or-later
"""Migration 0010 guesses the language of the items collected without one, and hands them
back to the watch."""

import uuid
from pathlib import Path

import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.platform import database as db
from otlet.platform import migrations
from otlet.platform.config import Settings

pytestmark = requires_database

FRENCH = (
    "Moins de faillites qu'en septembre, mais trois secteurs battent des records et les pertes"
    " d'emplois augmentent dans la région, selon les chiffres publiés pour le mois."
)


def test_items_without_language_get_one(migrated: TestDatabase, tmp_path: Path) -> None:
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=migrated.migrator_url)
    migrations.downgrade(settings, "0009")
    workspace, source = uuid.uuid4(), uuid.uuid4()
    told, short, declared = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with db.create_engine(migrated.admin_url).begin() as connection:
        run = connection.execute
        run(sa.text("INSERT INTO workspaces (id, name) VALUES (:w, 'W')"), {"w": workspace})
        run(
            sa.text(
                "INSERT INTO sources (id, workspace_id, name, url, feed_url, interval_minutes)"
                " VALUES (:s, :w, 'S', 'https://x.org/f', 'https://x.org/f', 60)"
            ),
            {"s": source, "w": workspace},
        )
        for item, title, text, language in (
            (told, "Faillites", FRENCH, None),
            (short, "MOTOCROSS des Nations", None, None),
            (declared, "Faillites", FRENCH, "nl"),
        ):
            run(
                sa.text(
                    "INSERT INTO source_items (id, workspace_id, source_id, origin, guid, title,"
                    " text, text_status, watched_at, language)"
                    " VALUES (:i, :w, :s, 'feed', :i, :title, :text, 'full_text', now(),"
                    " :language)"
                ),
                {
                    "i": item,
                    "w": workspace,
                    "s": source,
                    "title": title,
                    "text": text,
                    "language": language,
                },
            )
    migrations.upgrade(settings)
    with db.create_engine(migrated.admin_url).connect() as connection:
        rows = {
            row.id: (row.language, row.search_config, row.watched_at is None)
            for row in connection.execute(
                sa.text("SELECT id, language, search_config::text, watched_at FROM source_items")
            )
        }
    assert rows[told] == ("fr", "french", True)  # handed back to the watch
    assert rows[short] == (None, "simple", False)  # too short to tell: left as it was
    assert rows[declared] == ("nl", "simple", False)  # a declared language is never replaced
