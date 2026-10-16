# SPDX-License-Identifier: AGPL-3.0-or-later
"""Upgrade and downgrade on a real PostgreSQL, run by the migration role."""

from pathlib import Path

import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.platform import database as db
from otlet.platform import migrations, roles
from otlet.platform.config import Settings

pytestmark = requires_database


def test_upgrade_then_downgrade(database: TestDatabase, tmp_path: Path) -> None:
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=database.migrator_url)
    engine = db.create_engine(database.migrator_url)
    migrations.downgrade(settings, "base")

    migrations.upgrade(settings)
    assert db.schema_revision(engine) == "0010"

    migrations.downgrade(settings, "base")
    with engine.connect() as connection:
        assert sa.inspect(connection).get_table_names() == ["alembic_version"]
        functions = sa.text(
            "SELECT count(*) FROM pg_proc WHERE proname IN ('find_identity', 'find_session')"
        )
        assert connection.execute(functions).scalar() == 0


def test_migrations_create_objects_owned_by_the_owner_role(migrated: TestDatabase) -> None:
    with db.create_engine(migrated.migrator_url).connect() as connection:
        owners = connection.execute(
            sa.text("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
        assert set(owners) == {roles.OWNER}
