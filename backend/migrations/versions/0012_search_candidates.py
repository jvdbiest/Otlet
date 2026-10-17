# SPDX-License-Identifier: AGPL-3.0-or-later
"""The full-text search uses its index again (ADR-0033, P01).

Under row-level security, PostgreSQL only applies a condition that is not leakproof after the
policy, so `search @@ query` could not use the GIN index: every search read the whole table.
`search_candidates` belongs to `otlet_search`, which bypasses row-level security; it reads the
current workspace itself and returns the items of that workspace whose text matches, and
nothing without a workspace. The ranking, the triage and the topics stay under the policies.

Revision: 0012
Previous: 0011
"""

from alembic import op

from otlet.collection.domain.model import SEARCH_CONFIGS, SIMPLE_SEARCH
from otlet.platform import rls
from otlet.platform.roles import APP, SEARCH

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

FUNCTION = "search_candidates(text)"
# Every configuration an item may be indexed in (collection.domain.model.search_config): a new
# language needs a new migration of this function.
CONFIGS = (*dict.fromkeys(SEARCH_CONFIGS.values()), SIMPLE_SEARCH)
MATCHES = " OR ".join(
    f"i.search @@ websearch_to_tsquery('{config}'::regconfig, q)" for config in CONFIGS
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE FUNCTION search_candidates(q text) RETURNS SETOF uuid
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT i.id FROM public.source_items AS i
            WHERE i.workspace_id = {rls.CURRENT_WORKSPACE} AND ({MATCHES})
        $$
        """  # noqa: S608 (constant configuration names)
    )
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC")
    # The roles exist once the database is provisioned (M-12). Without them, the function
    # stays with the owner: still limited to the workspace, but slow (row-level security).
    op.execute(
        f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{SEARCH}') THEN
                GRANT SELECT (id, workspace_id, search) ON source_items TO {SEARCH};
                -- A new owner needs CREATE on the schema, for this change only.
                GRANT CREATE ON SCHEMA public TO {SEARCH};
                ALTER FUNCTION {FUNCTION} OWNER TO {SEARCH};
                REVOKE CREATE ON SCHEMA public FROM {SEARCH};
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP}') THEN
                GRANT EXECUTE ON FUNCTION {FUNCTION} TO {APP};
            END IF;
        END $$
        """  # noqa: S608 (constant role names)
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {FUNCTION}")
    op.execute(
        f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{SEARCH}') THEN
                REVOKE SELECT (id, workspace_id, search) ON source_items FROM {SEARCH};
            END IF;
        END $$
        """  # noqa: S608 (constant role names)
    )
