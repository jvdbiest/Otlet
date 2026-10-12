# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fixtures for integration tests on a real PostgreSQL (B05).

They run when OTLET_TEST_ADMIN_URL gives a superuser connection to a disposable database, in
libpq form (postgresql://postgres:postgres@localhost:5432/otlet_test); the CI provides one on
Linux. Without it, the tests that need a database are skipped.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from integration_support import ADMIN_URL, TestDatabase
from otlet.platform import migrations, roles
from otlet.platform.config import Settings

MIGRATOR_PASSWORD = "migrator-test-password"  # noqa: S105 (disposable test database)
APP_PASSWORD = "app-test-password"  # noqa: S105 (disposable test database)


def _sqlalchemy_url(libpq_url: str, user: str, password: str) -> str:
    url = make_url(libpq_url).set(drivername="postgresql+psycopg", username=user, password=password)
    return url.render_as_string(hide_password=False)


def _admin_credentials(libpq_url: str) -> tuple[str, str]:
    url = make_url(libpq_url)
    return url.username or "", url.password or ""


@pytest.fixture(scope="session")
def database() -> TestDatabase:
    """The test database, provisioned with the three roles of M-12."""
    assert ADMIN_URL is not None
    roles.provision(ADMIN_URL, MIGRATOR_PASSWORD, APP_PASSWORD)
    return TestDatabase(
        admin_url=_sqlalchemy_url(ADMIN_URL, *_admin_credentials(ADMIN_URL)),
        migrator_url=_sqlalchemy_url(ADMIN_URL, roles.MIGRATOR, MIGRATOR_PASSWORD),
        app_url=_sqlalchemy_url(ADMIN_URL, roles.APP, APP_PASSWORD),
    )


@pytest.fixture
def migrated(database: TestDatabase, tmp_path: Path) -> Iterator[TestDatabase]:
    """The schema at its latest revision, migrated by the migration role; dropped afterwards."""
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=database.migrator_url)
    migrations.downgrade(settings, "base")
    migrations.upgrade(settings)
    yield database
    migrations.downgrade(settings, "base")
