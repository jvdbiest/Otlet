# SPDX-License-Identifier: AGPL-3.0-or-later
"""Server-side sessions and the sign-in throttle (F02, ADR-0029).

- `user_sessions` keeps a SHA-256 digest of each session token, never the token itself. Its rows
  follow the user context; the cookie is resolved before any context exists, through the single
  function `find_session`.
- `auth_throttle` counts failed sign-ins per key (login, client address) in a fixed window. No
  context can read it: only its three functions, owned by the schema owner, touch it.

Revision: 0003
Previous: 0002
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

FUNCTIONS = (
    "find_session(bytea)",
    "auth_throttle_failures(text, interval)",
    "auth_throttle_record(text, interval)",
    "auth_throttle_clear(text)",
)
# Owner-only functions: fixed search path, no caller-controlled object resolution.
DEFINER = "SECURITY DEFINER SET search_path = pg_catalog, public"


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reauthenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.CheckConstraint("length(token_hash) = 32", name="user_sessions_token_hash_length"),
    )
    op.create_index("user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_table(
        "auth_throttle",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
    )

    statements = [
        *rls.enable(
            "user_sessions",
            using=f"user_id = {rls.CURRENT_USER_ID} OR {rls.AS_OWNER}",
            check=f"user_id = {rls.CURRENT_USER_ID}",
        ),
        *rls.enable("auth_throttle", using=rls.AS_OWNER),
        f"""
        CREATE FUNCTION find_session(p_token_hash bytea)
        RETURNS TABLE (session_id uuid, user_id uuid, created_at timestamptz,
                       last_seen_at timestamptz, reauthenticated_at timestamptz,
                       disabled boolean)
        LANGUAGE sql STABLE {DEFINER}
        AS $$
            SELECT s.id, s.user_id, s.created_at, s.last_seen_at, s.reauthenticated_at,
                   u.disabled_at IS NOT NULL
            FROM user_sessions AS s JOIN users AS u ON u.id = s.user_id
            WHERE s.token_hash = p_token_hash
        $$
        """,  # noqa: S608 (constant DEFINER clause)
        f"""
        CREATE FUNCTION auth_throttle_failures(p_key text, p_window interval)
        RETURNS integer
        LANGUAGE sql STABLE {DEFINER}
        AS $$
            SELECT coalesce(
                (SELECT failures FROM auth_throttle
                 WHERE key = p_key AND window_start > now() - p_window), 0)
        $$
        """,  # noqa: S608 (constant DEFINER clause)
        f"""
        CREATE FUNCTION auth_throttle_record(p_key text, p_window interval)
        RETURNS integer
        LANGUAGE sql {DEFINER}
        AS $$
            INSERT INTO auth_throttle AS t (key, window_start, failures)
            VALUES (p_key, now(), 1)
            ON CONFLICT (key) DO UPDATE SET
                failures = CASE WHEN t.window_start > now() - p_window
                                THEN t.failures + 1 ELSE 1 END,
                window_start = CASE WHEN t.window_start > now() - p_window
                                    THEN t.window_start ELSE now() END
            RETURNING failures
        $$
        """,  # noqa: S608 (constant DEFINER clause)
        f"""
        CREATE FUNCTION auth_throttle_clear(p_key text)
        RETURNS void
        LANGUAGE sql {DEFINER}
        AS $$ DELETE FROM auth_throttle WHERE key = p_key $$
        """,  # noqa: S608 (constant DEFINER clause)
        *(rls.grant_to_app(function) for function in FUNCTIONS),
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION {function}")
    op.drop_table("auth_throttle")
    op.drop_table("user_sessions")
