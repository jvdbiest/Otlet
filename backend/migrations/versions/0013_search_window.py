# SPDX-License-Identifier: AGPL-3.0-or-later
"""The window of the search is taken where the index is used (ADR-0033, P01b).

P01b showed that once `search_candidates` used the index, the time went into the window of
the 1,000 most recent candidates: it was taken after the function, under row-level security,
by reading every candidate again one by one (19,483 index lookups for a frequent word). The
function now returns the date of each candidate and leaves out the copies of a story already
there, and takes the window itself when it is given one. With a topic filter, which reads the
matches under the policies, the window is still taken after it.

Revision: 0013
Previous: 0012
"""

from alembic import op

from otlet.collection.domain.model import SEARCH_CONFIGS, SIMPLE_SEARCH
from otlet.platform import rls
from otlet.platform.roles import APP, SEARCH

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

OLD = "search_candidates(text)"
FUNCTION = "search_candidates(text, integer)"
COLUMNS = "published_at, collected_at, duplicate_of"
CONFIGS = (*dict.fromkeys(SEARCH_CONFIGS.values()), SIMPLE_SEARCH)
MATCHES = " OR ".join(
    f"i.search @@ websearch_to_tsquery('{config}'::regconfig, q)" for config in CONFIGS
)


def _hand_over(function: str) -> str:
    """Gives the function to the search role, and its use to the application role, once
    the database is provisioned (M-12)."""
    return f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{SEARCH}') THEN
                GRANT SELECT ({COLUMNS}) ON source_items TO {SEARCH};
                -- A new owner needs CREATE on the schema, for this change only.
                GRANT CREATE ON SCHEMA public TO {SEARCH};
                ALTER FUNCTION {function} OWNER TO {SEARCH};
                REVOKE CREATE ON SCHEMA public FROM {SEARCH};
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP}') THEN
                GRANT EXECUTE ON FUNCTION {function} TO {APP};
            END IF;
        END $$
    """  # noqa: S608 (constant role names)


def upgrade() -> None:
    op.execute(f"DROP FUNCTION {OLD}")
    op.execute(
        f"""
        CREATE FUNCTION search_candidates(q text, window_size integer)
        RETURNS TABLE (id uuid, workspace_id uuid, sort_date timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT i.id, i.workspace_id,
                least(coalesce(i.published_at, i.collected_at), i.collected_at)
            FROM public.source_items AS i
            WHERE i.workspace_id = {rls.CURRENT_WORKSPACE} AND i.duplicate_of IS NULL
              AND ({MATCHES})
            ORDER BY 3 DESC
            LIMIT window_size
        $$
        """  # noqa: S608 (constant configuration names)
    )
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC")
    op.execute(_hand_over(FUNCTION))


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {FUNCTION}")
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
    op.execute(f"REVOKE ALL ON FUNCTION {OLD} FROM PUBLIC")
    op.execute(_hand_over(OLD))
