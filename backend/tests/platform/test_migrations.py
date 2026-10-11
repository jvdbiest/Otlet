# SPDX-License-Identifier: AGPL-3.0-or-later
"""Upgrade and downgrade on a real PostgreSQL. Runs when OTLET_TEST_DATABASE_URL points to a
disposable database; the CI PostgreSQL service arrives with B05, the Compose job covers the
same path meanwhile."""

import os
from pathlib import Path

import pytest
import sqlalchemy as sa

from otlet.platform import database, migrations
from otlet.platform.config import Settings

DATABASE_URL = os.environ.get("OTLET_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(DATABASE_URL is None, reason="OTLET_TEST_DATABASE_URL not set")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    assert DATABASE_URL is not None
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=DATABASE_URL)
    migrations.downgrade(settings, "base")
    return settings


def test_upgrade_then_downgrade(settings: Settings) -> None:
    engine = database.create_engine(settings.require_database_url())
    assert database.schema_revision(engine) in (None, "")

    migrations.upgrade(settings)
    assert database.schema_revision(engine) == "0001"
    with engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO instance_settings (key, value) VALUES ('k', '1'::jsonb)")
        )

    migrations.downgrade(settings, "base")
    with engine.connect() as connection:
        assert not sa.inspect(connection).has_table("instance_settings")
