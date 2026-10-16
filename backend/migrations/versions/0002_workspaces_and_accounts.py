# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workspaces, accounts with several identities, and memberships (F01, ADR-0028).

- An account (`users`) belongs to the instance, not to a workspace. It signs in through one or
  more identities (`user_identities`): a password today, OpenID Connect or a security key later,
  without changing the account (ROADMAP §5.2, ARCHITECTURE §19.2).
- A workspace (`workspaces`) is the unit of isolation; `workspace_members` gives an account a
  role in it (ARCHITECTURE §19.3).
- Row-level security is forced on every table. The business tables read the workspace context;
  the account tables read the user context. Signing in, before any context exists, goes through
  the single function `find_identity`, owned by the schema owner.

Revision: 0002
Previous: 0001
"""

import uuid

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls
from otlet.platform.roles import APP

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ROLES = ("owner", "editor", "validator", "observer")
CREATED_AT = {"nullable": False, "server_default": sa.func.now()}


def _id() -> "sa.Column[uuid.UUID]":
    # UUIDv7: opaque, not sequential, sortable in time (ARCHITECTURE §8.5, PostgreSQL 18).
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuidv7()"))


def upgrade() -> None:
    op.create_table(
        "workspaces",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), **CREATED_AT),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 200", name="workspaces_name_length"),
    )
    op.create_table(
        "users",
        _id(),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=False, server_default="fr"),
        sa.Column("is_instance_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), **CREATED_AT),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(display_name) BETWEEN 1 AND 200", name="users_display_name_length"
        ),
    )
    op.create_table(
        "user_identities",
        _id(),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # password, oidc, webauthn…: the identity module knows the kinds; the schema only keeps
        # them well formed, so a new kind needs no migration.
        sa.Column("kind", sa.Text(), nullable=False),
        # Empty for local identities; the issuer URL for OpenID Connect.
        sa.Column("issuer", sa.Text(), nullable=False, server_default=""),
        # The normalised login (lower-case e-mail address) or the provider's subject.
        sa.Column("subject", sa.Text(), nullable=False),
        # A password hash or a public key; never a secret that could be replayed as is.
        sa.Column("credential", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), **CREATED_AT),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind ~ '^[a-z][a-z0-9_]{0,31}$'", name="user_identities_kind"),
        sa.CheckConstraint(
            "length(subject) BETWEEN 1 AND 320", name="user_identities_subject_length"
        ),
        sa.UniqueConstraint("kind", "issuer", "subject", name="user_identities_login"),
    )
    op.create_index("user_identities_user_id", "user_identities", ["user_id"])
    op.create_table(
        "workspace_members",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), **CREATED_AT),
        sa.CheckConstraint(
            "role IN (" + ", ".join(f"'{role}'" for role in ROLES) + ")",
            name="workspace_members_role",
        ),
    )
    op.create_index("workspace_members_user_id", "workspace_members", ["user_id"])

    # Built from constant expressions only, no input (S608).
    my_workspaces = (
        f"SELECT workspace_id FROM workspace_members WHERE user_id = {rls.CURRENT_USER_ID}"  # noqa: S608
    )
    fellow_members = (
        f"SELECT user_id FROM workspace_members WHERE workspace_id = {rls.CURRENT_WORKSPACE}"  # noqa: S608
    )
    statements = [
        # The current workspace, plus the names of the user's other workspaces (to switch).
        *rls.enable(
            "workspaces",
            using=f"id = {rls.CURRENT_WORKSPACE} OR id IN ({my_workspaces})",
            check=f"id = {rls.CURRENT_WORKSPACE}",
        ),
        # The workspace's memberships, plus the user's own (the list of their workspaces).
        *rls.enable(
            "workspace_members",
            using=(f"workspace_id = {rls.CURRENT_WORKSPACE} OR user_id = {rls.CURRENT_USER_ID}"),
            check=f"workspace_id = {rls.CURRENT_WORKSPACE}",
        ),
        # The user's own account, plus the members of the current workspace (names only are
        # shown); the sign-in lookup reads as the owner.
        *rls.enable(
            "users",
            using=(f"id = {rls.CURRENT_USER_ID} OR id IN ({fellow_members}) OR {rls.AS_OWNER}"),
            check=f"id = {rls.CURRENT_USER_ID}",
        ),
        *rls.enable(
            "user_identities",
            using=f"user_id = {rls.CURRENT_USER_ID} OR {rls.AS_OWNER}",
            check=f"user_id = {rls.CURRENT_USER_ID}",
        ),
        # Sign-in: the one way to read an identity without a user context. It returns the
        # identity found by its login and nothing else.
        """
        CREATE FUNCTION find_identity(p_kind text, p_issuer text, p_subject text)
        RETURNS TABLE (identity_id uuid, user_id uuid, credential text, disabled boolean)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT i.id, i.user_id, i.credential, u.disabled_at IS NOT NULL
            FROM user_identities AS i JOIN users AS u ON u.id = i.user_id
            WHERE i.kind = p_kind AND i.issuer = p_issuer AND i.subject = p_subject
        $$
        """,
        "REVOKE ALL ON FUNCTION find_identity(text, text, text) FROM PUBLIC",
        # The application role exists once the database is provisioned (M-12); provisioning
        # grants it later otherwise (otlet.platform.roles).
        f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP}') THEN
                GRANT EXECUTE ON FUNCTION find_identity(text, text, text) TO {APP};
            END IF;
        END $$
        """,  # noqa: S608 (constant role name)
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP FUNCTION find_identity(text, text, text)")
    # These two policies read workspace_members, which cannot be dropped before them.
    for table in ("users", "workspaces"):
        op.execute(f"DROP POLICY {rls.POLICY} ON {table}")
    for table in ("workspace_members", "user_identities", "users", "workspaces"):
        op.drop_table(table)
