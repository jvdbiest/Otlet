# SPDX-License-Identifier: AGPL-3.0-or-later
"""One full-text query for every language of the search (ADR-0034, P01c).

`search_candidates` tested the text with eight conditions joined by OR, one per language
configuration. For most words, several of them give the same lexeme; the planner added up
their estimates, expected several times too many items, and then read the whole table. The
eight queries are now computed once, without duplicates, and joined into a single tsquery
(`a | b | …`) tested by a single condition, which the GIN index always serves.

Revision: 0014
Previous: 0013
"""

from alembic import op

from otlet.collection.domain.model import SEARCH_CONFIGS, SIMPLE_SEARCH
from otlet.platform import rls

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

CONFIGS = (*dict.fromkeys(SEARCH_CONFIGS.values()), SIMPLE_SEARCH)
QUERIES = ", ".join(f"websearch_to_tsquery('{config}'::regconfig, q)" for config in CONFIGS)
# The queries of every configuration, each once, joined by OR; NULL when none has a lexeme
# (only stop words), and then nothing matches.
MERGED = (
    "(SELECT string_agg(DISTINCT '(' || t::text || ')', ' | ')::tsquery"  # noqa: S608
    f" FROM unnest(ARRAY[{QUERIES}]) AS t WHERE numnode(t) > 0)"
)
SEPARATE = " OR ".join(
    f"i.search @@ websearch_to_tsquery('{config}'::regconfig, q)" for config in CONFIGS
)


def _replace(condition: str) -> None:
    # The function keeps its owner, its rights and its signature (migrations 0012 and 0013).
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION search_candidates(q text, window_size integer)
        RETURNS TABLE (id uuid, workspace_id uuid, sort_date timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT i.id, i.workspace_id,
                least(coalesce(i.published_at, i.collected_at), i.collected_at)
            FROM public.source_items AS i
            WHERE i.workspace_id = {rls.CURRENT_WORKSPACE} AND i.duplicate_of IS NULL
              AND ({condition})
            ORDER BY 3 DESC
            LIMIT window_size
        $$
        """  # noqa: S608 (constant configuration names)
    )


def upgrade() -> None:
    _replace(f"i.search @@ {MERGED}")


def downgrade() -> None:
    _replace(SEPARATE)
