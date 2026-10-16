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


def test_provisioning_takes_over_what_a_superuser_created(database: TestDatabase) -> None:
    """An installation that ran as the superuser before M-12 reached the stack: its objects
    move to the owner, and the application role can still use them."""
    from conftest import APP_PASSWORD, MIGRATOR_PASSWORD
    from integration_support import ADMIN_URL

    assert ADMIN_URL is not None
    admin = db.create_engine(database.admin_url)
    with admin.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TYPE legacy_state AS ENUM ('a', 'b');"
                " CREATE TABLE legacy_jobs (id bigserial PRIMARY KEY, state legacy_state);"
                " CREATE SEQUENCE legacy_counter;"
                " CREATE FUNCTION legacy_next() RETURNS bigint LANGUAGE sql"
                "  AS 'SELECT nextval(''legacy_counter'')'"
            )
        )
    try:
        roles.provision(ADMIN_URL, MIGRATOR_PASSWORD, APP_PASSWORD)
        with admin.connect() as connection:
            owners = (
                connection.execute(
                    sa.text(
                        "SELECT pg_get_userbyid(relowner) FROM pg_class"
                        " WHERE relname IN ('legacy_jobs', 'legacy_jobs_id_seq', 'legacy_counter')"
                        " UNION ALL SELECT pg_get_userbyid(typowner) FROM pg_type"
                        " WHERE typname = 'legacy_state'"
                        " UNION ALL SELECT pg_get_userbyid(proowner) FROM pg_proc"
                        " WHERE proname = 'legacy_next'"
                    )
                )
                .scalars()
                .all()
            )
        assert set(owners) == {roles.OWNER} and len(owners) == 5
        with db.create_engine(database.app_url).begin() as connection:
            connection.execute(sa.text("INSERT INTO legacy_jobs (state) VALUES ('a')"))
            assert connection.execute(sa.text("SELECT legacy_next()")).scalar() == 1
    finally:
        with admin.begin() as connection:
            connection.execute(
                sa.text(
                    "DROP FUNCTION legacy_next(); DROP SEQUENCE legacy_counter;"
                    " DROP TABLE legacy_jobs; DROP TYPE legacy_state"
                )
            )
