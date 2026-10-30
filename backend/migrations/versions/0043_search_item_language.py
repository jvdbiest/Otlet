# SPDX-License-Identifier: AGPL-3.0-or-later
"""A term is read in the language of the item (Joël's question on the weather, 2026-10-30).

The query of every language was tested against every item: « showers » is « show » for the German
stemmer, and matched the Echo Show and every concert of a French corpus; « moto » is « mot » for
the Spanish one. On the 744 terms of the Reporter so far, 52 lost articles this way, nearly all
without any link (« informeren », 553 articles to 0). An item now holds a term in its own
language, in English (the third language of the terms the model gives: « hacking » finds « hack »),
or without accents (« Jorge Martin » for « Jorge Martín », « België » for « Belgie »).

The merged query of ADR-0034 stays: it alone uses the index, and the condition below only rereads
the items it found.

Revision: 0043
Previous: 0042
"""

from alembic import op

from otlet.collection.domain.model import SEARCH_CONFIGS, SIMPLE_SEARCH
from otlet.platform import rls
from otlet.platform.roles import SEARCH

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

CONFIGS = (*dict.fromkeys(SEARCH_CONFIGS.values()), SIMPLE_SEARCH)
FOLDED = (
    "translate(q, 'àâäáãéèêëíìîïóòôöõúùûüçñÀÂÄÁÃÉÈÊËÍÌÎÏÓÒÔÖÕÚÙÛÜÇÑ',"
    " 'aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN')"
)
QUERIES = ", ".join(f"websearch_to_tsquery('{config}'::regconfig, q)" for config in CONFIGS)
FOLDED_QUERIES = ", ".join(
    f"websearch_to_tsquery('{config}'::regconfig, {FOLDED})" for config in CONFIGS
)


def merged(queries: str) -> str:
    return (
        "(SELECT string_agg(DISTINCT '(' || t::text || ')', ' | ')::tsquery"  # noqa: S608
        f" FROM unnest(ARRAY[{queries}]) AS t WHERE numnode(t) > 0)"
    )


IN_ITS_LANGUAGE = (
    "(i.search @@ websearch_to_tsquery(i.search_config, q)"
    " OR i.search @@ websearch_to_tsquery('english'::regconfig, q)"
    f" OR i.search @@ websearch_to_tsquery(i.search_config, {FOLDED}))"
)


def _replace(condition: str) -> None:
    # The function keeps its owner, its rights and its signature (migrations 0012 to 0014).
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


def _columns(change: str) -> None:
    # The search role reads only the columns it needs, once the database is provisioned (M-12).
    op.execute(
        f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{SEARCH}') THEN
                {change};
            END IF;
        END $$
        """  # noqa: S608 (constant role names)
    )


def upgrade() -> None:
    _columns(f"GRANT SELECT (search_config) ON source_items TO {SEARCH}")
    _replace(f"i.search @@ {merged(QUERIES + ', ' + FOLDED_QUERIES)} AND {IN_ITS_LANGUAGE}")


def downgrade() -> None:
    _replace(f"i.search @@ {merged(QUERIES)}")
    _columns(f"REVOKE SELECT (search_config) ON source_items FROM {SEARCH}")  # noqa: S608
