# SPDX-License-Identifier: AGPL-3.0-or-later
"""The application role of M-12 reads and writes rows, and nothing more (B05)."""

import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.platform import database as db
from otlet.platform import roles

pytestmark = requires_database


def test_application_role_cannot_create_a_table(migrated: TestDatabase) -> None:
    with db.create_engine(migrated.app_url).connect() as connection:
        with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
            connection.execute(sa.text("CREATE TABLE intruder (id int)"))


def test_application_role_reads_and_writes_rows(migrated: TestDatabase) -> None:
    with db.create_engine(migrated.app_url).begin() as connection:
        connection.execute(
            sa.text("INSERT INTO instance_settings (key, value) VALUES ('k', '1'::jsonb)")
        )
        assert connection.execute(sa.text("SELECT count(*) FROM instance_settings")).scalar() == 1
        connection.execute(sa.text("DELETE FROM instance_settings"))


def test_application_role_cannot_alter_or_drop_tables(migrated: TestDatabase) -> None:
    with db.create_engine(migrated.app_url).connect() as connection:
        with pytest.raises(sa.exc.ProgrammingError, match="must be owner"):
            connection.execute(sa.text("DROP TABLE instance_settings"))


def test_application_role_has_no_bypass(database: TestDatabase) -> None:
    with db.create_engine(database.admin_url).connect() as connection:
        row = connection.execute(
            sa.text(
                "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolinherit"
                " FROM pg_roles WHERE rolname = :name"
            ),
            {"name": roles.APP},
        ).one()
    assert tuple(row) == (False, False, False, False, False)


def test_provisioning_is_idempotent(database: TestDatabase) -> None:
    from conftest import APP_PASSWORD, MIGRATOR_PASSWORD
    from integration_support import ADMIN_URL

    assert ADMIN_URL is not None
    roles.provision(ADMIN_URL, MIGRATOR_PASSWORD, APP_PASSWORD)
    roles.provision(ADMIN_URL, MIGRATOR_PASSWORD, APP_PASSWORD)
