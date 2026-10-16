# SPDX-License-Identifier: AGPL-3.0-or-later
"""Row-level security policies, the second isolation barrier (ARCHITECTURE §8.1, ADR-0021,
ADR-0028). Migrations build their policies from these expressions, so every table reads the
context the same way as otlet.platform.database sets it.

Two contexts exist, both local to a transaction: the workspace (`app.workspace_id`) for the
business tables, the user (`app.user_id`) for the instance-level account tables. An empty or
missing setting is NULL, and NULL lets no row through.
"""

from otlet.platform.database import USER_SETTING, WORKSPACE_SETTING
from otlet.platform.roles import APP, OWNER

CURRENT_WORKSPACE = f"NULLIF(current_setting('{WORKSPACE_SETTING}', true), '')::uuid"
CURRENT_USER_ID = f"NULLIF(current_setting('{USER_SETTING}', true), '')::uuid"
# True only inside a SECURITY DEFINER function of the schema owner (the login lookup): the
# application role is not a member of the owner role and cannot take it.
AS_OWNER = f"current_user = '{OWNER}'"

POLICY = "isolation"


def enable(table: str, using: str, check: str | None = None) -> list[str]:
    """Statements that force row-level security on `table` with one policy for every command.
    `check` defaults to `using`; it may be narrower, never wider."""
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY {POLICY} ON {table} USING ({using}) WITH CHECK ({check or using})",
    ]


def grant_to_app(function: str) -> str:
    """Lets the application role call `function` (a signature such as `f(text)`), when the role
    exists; provisioning grants it otherwise (otlet.platform.roles)."""
    return f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP}') THEN
                REVOKE ALL ON FUNCTION {function} FROM PUBLIC;
                GRANT EXECUTE ON FUNCTION {function} TO {APP};
            END IF;
        END $$
        """  # noqa: S608 (constant names only)


def workspace_scoped(table: str, column: str = "workspace_id") -> list[str]:
    """The policy of a business table: the rows of the current workspace, nothing else."""
    return enable(table, f"{column} = {CURRENT_WORKSPACE}")
