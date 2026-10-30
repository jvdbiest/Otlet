# SPDX-License-Identifier: AGPL-3.0-or-later
"""The meaning of each item (ADR-0045, sens-1): a vector of a small multilingual model, so that
« les hôpitaux en Flandre » finds « Vlaamse ziekenhuizen » with no word in common. The model
that made it is kept with it: another model gives vectors that do not compare.

Revision: 0041
Previous: 0040
"""

from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

DIMENSIONS = 384
UNMEANT = "unmeant_items(integer)"


def upgrade() -> None:
    # Provisioned with the roles of M-12 (otlet.platform.roles); created here for a database
    # that was not, when the migration role may (a no-op otherwise).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"ALTER TABLE source_items ADD COLUMN meaning vector({DIMENSIONS})")
    op.execute("ALTER TABLE source_items ADD COLUMN meaning_model text")
    op.execute(
        "CREATE INDEX source_items_meaning ON source_items USING hnsw (meaning vector_cosine_ops)"
    )
    # The items left to encode, the most recent first.
    op.execute(
        "CREATE INDEX source_items_unmeant ON source_items (collected_at DESC)"
        " WHERE meaning IS NULL AND duplicate_of IS NULL AND text_status <> 'pending'"
    )
    # The items without a vector, in every workspace, with the text to encode. Only the
    # encoding job calls it; the owner exception of the policy (migration 0006) lets it read.
    op.execute(
        """
        CREATE FUNCTION unmeant_items(p_limit integer)
        RETURNS TABLE (workspace_id uuid, item_id uuid, title text, summary text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
        AS $$
            SELECT workspace_id, id, coalesce(title, ''), coalesce(summary, '')
            FROM source_items
            WHERE meaning IS NULL AND duplicate_of IS NULL AND text_status <> 'pending'
            ORDER BY collected_at DESC LIMIT p_limit
        $$
        """
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {UNMEANT}")
    op.execute("DROP INDEX source_items_unmeant")
    op.execute("DROP INDEX source_items_meaning")
    op.execute("ALTER TABLE source_items DROP COLUMN meaning_model")
    op.execute("ALTER TABLE source_items DROP COLUMN meaning")
