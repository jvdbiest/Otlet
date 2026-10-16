# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workspaces, accounts and identities (F01, ADR-0028): forced row-level security on every
table, an account with several identities, and sign-in through `find_identity` only."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.platform import database as db

pytestmark = requires_database

# Tables outside row-level security, each with its reason.
INSTANCE_TABLES = {
    "alembic_version": "schema state, read by the migration role",
    "instance_settings": "instance settings, no workspace (ARCHITECTURE §20.3)",
}
# The job queue: arguments are identifiers, never business data (ADR-0022, migration 0004).
QUEUE_TABLE_PREFIX = "procrastinate_"
ACCOUNT_TABLES = ("workspaces", "users", "user_identities", "workspace_members")


@dataclass(frozen=True)
class Accounts:
    app: sa.Engine
    alice: uuid.UUID
    bob: uuid.UUID
    workspace_a: uuid.UUID
    workspace_b: uuid.UUID


def _create_user(app: sa.Engine, name: str, login: str) -> uuid.UUID:
    user = uuid.uuid4()
    with db.scoped_transaction(app, user_id=user) as connection:
        connection.execute(
            sa.text("INSERT INTO users (id, display_name) VALUES (:id, :name)"),
            {"id": user, "name": name},
        )
        connection.execute(
            sa.text(
                "INSERT INTO user_identities (user_id, kind, subject, credential)"
                " VALUES (:user, 'password', :login, 'hash')"
            ),
            {"user": user, "login": login},
        )
    return user


def _create_workspace(app: sa.Engine, name: str, owner: uuid.UUID) -> uuid.UUID:
    workspace = uuid.uuid4()
    with db.scoped_transaction(app, workspace_id=workspace, user_id=owner) as connection:
        connection.execute(
            sa.text("INSERT INTO workspaces (id, name) VALUES (:id, :name)"),
            {"id": workspace, "name": name},
        )
        connection.execute(
            sa.text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " VALUES (:workspace, :user, 'owner')"
            ),
            {"workspace": workspace, "user": owner},
        )
    return workspace


@pytest.fixture
def accounts(migrated: TestDatabase) -> Iterator[Accounts]:
    """Alice owns workspace A, Bob owns workspace B; neither belongs to the other's."""
    app = db.create_engine(migrated.app_url)
    alice = _create_user(app, "Alice", "alice@example.org")
    bob = _create_user(app, "Bob", "bob@example.org")
    yield Accounts(
        app=app,
        alice=alice,
        bob=bob,
        workspace_a=_create_workspace(app, "A", alice),
        workspace_b=_create_workspace(app, "B", bob),
    )


def _count(connection: sa.Connection, table: str) -> int:
    return int(connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


def test_every_table_has_forced_row_level_security(migrated: TestDatabase) -> None:
    with db.create_engine(migrated.admin_url).connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity"
                " FROM pg_class AS c JOIN pg_namespace AS n ON n.oid = c.relnamespace"
                " WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')"
            )
        ).all()
    unprotected = {
        name
        for name, enabled, forced in rows
        if not (enabled and forced) and not name.startswith(QUEUE_TABLE_PREFIX)
    } - INSTANCE_TABLES.keys()
    assert unprotected == set()
    assert set(ACCOUNT_TABLES) <= {name for name, _, _ in rows}


def test_without_context_every_account_table_is_empty(accounts: Accounts) -> None:
    with accounts.app.connect() as connection:
        assert {table: _count(connection, table) for table in ACCOUNT_TABLES} == dict.fromkeys(
            ACCOUNT_TABLES, 0
        )


def test_an_account_carries_several_identities(accounts: Accounts) -> None:
    with db.scoped_transaction(accounts.app, user_id=accounts.alice) as connection:
        connection.execute(
            sa.text(
                "INSERT INTO user_identities (user_id, kind, issuer, subject)"
                " VALUES (:user, 'oidc', 'https://id.example.org', 'alice-sub')"
            ),
            {"user": accounts.alice},
        )
        kinds = connection.execute(
            sa.text("SELECT kind FROM user_identities ORDER BY kind")
        ).scalars()
        assert list(kinds) == ["oidc", "password"]


def test_a_login_belongs_to_one_identity(accounts: Accounts) -> None:
    with pytest.raises(sa.exc.IntegrityError, match="user_identities_login"):
        _create_user(accounts.app, "Mallory", "alice@example.org")


def test_sign_in_finds_the_identity_without_a_context(accounts: Accounts) -> None:
    with accounts.app.connect() as connection:
        found = connection.execute(
            sa.text("SELECT user_id, credential, disabled FROM find_identity('password', '', :s)"),
            {"s": "alice@example.org"},
        ).one()
        missing = connection.execute(
            sa.text("SELECT count(*) FROM find_identity('password', '', 'nobody@example.org')")
        ).scalar_one()
    assert tuple(found) == (accounts.alice, "hash", False)
    assert missing == 0


def test_a_user_sees_only_their_own_account_and_identities(accounts: Accounts) -> None:
    with db.scoped_transaction(accounts.app, user_id=accounts.alice) as connection:
        users = connection.execute(sa.text("SELECT id FROM users")).scalars()
        identities = connection.execute(sa.text("SELECT user_id FROM user_identities")).scalars()
        assert list(users) == [accounts.alice]
        assert list(identities) == [accounts.alice]


def test_a_user_lists_their_workspaces_and_no_other(accounts: Accounts) -> None:
    with db.scoped_transaction(accounts.app, user_id=accounts.alice) as connection:
        workspaces = connection.execute(sa.text("SELECT id FROM workspaces")).scalars()
        assert list(workspaces) == [accounts.workspace_a]


def test_a_workspace_context_shows_its_members_only(accounts: Accounts) -> None:
    with db.scoped_transaction(
        accounts.app, workspace_id=accounts.workspace_b, user_id=accounts.bob
    ) as connection:
        members = connection.execute(sa.text("SELECT user_id FROM workspace_members")).scalars()
        names = connection.execute(sa.text("SELECT display_name FROM users")).scalars()
        assert list(members) == [accounts.bob]
        assert list(names) == ["Bob"]


def test_cannot_join_another_workspace(accounts: Accounts) -> None:
    with pytest.raises(sa.exc.ProgrammingError, match="row-level security"):
        with db.scoped_transaction(
            accounts.app, workspace_id=accounts.workspace_a, user_id=accounts.bob
        ) as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO workspace_members (workspace_id, user_id, role)"
                    " VALUES (:workspace, :user, 'owner')"
                ),
                {"workspace": accounts.workspace_b, "user": accounts.bob},
            )


def test_cannot_add_an_identity_to_another_account(accounts: Accounts) -> None:
    with pytest.raises(sa.exc.ProgrammingError, match="row-level security"):
        with db.scoped_transaction(accounts.app, user_id=accounts.bob) as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO user_identities (user_id, kind, subject)"
                    " VALUES (:user, 'password', 'takeover@example.org')"
                ),
                {"user": accounts.alice},
            )


def test_roles_are_limited_to_the_known_ones(accounts: Accounts) -> None:
    with pytest.raises(sa.exc.IntegrityError, match="workspace_members_role"):
        with db.scoped_transaction(
            accounts.app, workspace_id=accounts.workspace_a, user_id=accounts.alice
        ) as connection:
            connection.execute(
                sa.text("UPDATE workspace_members SET role = 'superuser' WHERE user_id = :user"),
                {"user": accounts.alice},
            )


def test_identifiers_are_uuidv7_by_default(accounts: Accounts) -> None:
    with db.scoped_transaction(accounts.app, user_id=accounts.alice) as connection:
        identity = connection.execute(
            sa.text("SELECT id FROM user_identities WHERE kind = 'password'")
        ).scalar_one()
    assert identity.version == 7
