# SPDX-License-Identifier: AGPL-3.0-or-later
"""A backup and a restore against a real PostgreSQL, with pg_dump and pg_restore (F08:
« Restauration verte en CI »). Skipped where the client tools are missing; the CI installs them."""

import shutil
from pathlib import Path

import pytest
import sqlalchemy as sa

from integration_support import ADMIN_URL, TestDatabase, requires_database
from otlet.backup.adapters.crypto import Cipher
from otlet.backup.adapters.postgres import PostgresDatabase
from otlet.backup.application.backups import Backups
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces

pytestmark = [
    requires_database,
    pytest.mark.skipif(shutil.which("pg_dump") is None, reason="PostgreSQL client tools missing"),
]


def test_a_backup_restores_the_whole_instance(migrated: TestDatabase, tmp_path: Path) -> None:
    assert ADMIN_URL is not None
    engine = db.create_engine(migrated.app_url)
    auth = Authentication(PostgresIdentityStore(engine), Argon2Hasher())
    workspaces = Workspaces(PostgresWorkspaceStore(engine))
    user = auth.create_user("dora@example.org", "Dora", "une phrase de passe assez longue")
    workspace = workspaces.create(user, "Avant")
    files = tmp_path / "files"
    files.mkdir()
    destination = tmp_path / "backups"
    destination.mkdir()
    database = PostgresDatabase(ADMIN_URL)
    backups = Backups(
        destination,
        database,
        files,
        Cipher.for_destination(destination, "une phrase de passe assez longue"),
    )
    name = backups.run("manual")
    manifest = backups.manifest(name)
    assert manifest.verified, manifest.problems
    assert manifest.schema_revision == database.schema_revision() != ""
    # Then a workspace is lost, and another one appears: the restore brings back the state
    # of the backup, whole.
    admin = sa.create_engine(migrated.admin_url)
    with admin.begin() as connection:
        connection.execute(sa.text("DELETE FROM workspaces WHERE id = :id"), {"id": workspace.id})
    workspaces.create(user, "Après")
    admin.dispose()
    engine.dispose()
    safety = backups.restore(name)
    admin = sa.create_engine(migrated.admin_url)
    with admin.connect() as connection:
        names = connection.execute(sa.text("SELECT name FROM workspaces ORDER BY name")).scalars()
        assert list(names) == ["Avant"]
    admin.dispose()
    assert backups.manifest(safety).reason == "before-restore"
