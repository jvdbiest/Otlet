# SPDX-License-Identifier: AGPL-3.0-or-later
"""Topics, explained matches, duplicates and full-text search (U02).

- `source_items` gains its language, the text search configuration that follows from it, a
  fingerprint of its text and the item it duplicates, if any. `search` is the full-text vector
  of what Otlet may use: title (A), summary (B), and the text only when it may be kept (C).
- `topics`: the subjects of the watch, with their keywords, exclusions, languages and sources.
- `topic_matches`: the lexical score of an item for a topic and its explanation (F-VEI-02).

Revision: 0006
Previous: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from otlet.platform import rls

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

UNWATCHED = "unwatched_items(integer, interval)"
IN_WORKSPACE = f"workspace_id = {rls.CURRENT_WORKSPACE}"
SEARCH = (
    "setweight(to_tsvector(search_config, coalesce(title, '')), 'A')"
    " || setweight(to_tsvector(search_config, coalesce(summary, '')), 'B')"
    " || setweight(to_tsvector(search_config, left(CASE WHEN text_status IN"
    " ('full_text', 'manual') THEN coalesce(text, feed_content, '') ELSE '' END, 200000)), 'C')"
)


def upgrade() -> None:
    # Provisioned with the roles of M-12 (otlet.platform.roles); created here for a database
    # that was not, when the migration role may (a no-op otherwise).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column("source_items", sa.Column("language", sa.Text(), nullable=True))
    op.add_column(
        "source_items",
        sa.Column(
            "search_config",
            postgresql.REGCONFIG(),
            nullable=False,
            server_default=sa.text("'simple'::regconfig"),
        ),
    )
    op.add_column("source_items", sa.Column("content_hash", sa.LargeBinary(), nullable=True))
    # Set once the watch has handled the item; the catch-up job looks for the others.
    op.add_column(
        "source_items", sa.Column("watched_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "source_items",
        sa.Column(
            "duplicate_of",
            sa.Uuid(),
            sa.ForeignKey("source_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "source_items",
        sa.Column("search", postgresql.TSVECTOR(), sa.Computed(SEARCH, persisted=True)),
    )
    op.create_index("source_items_search", "source_items", ["search"], postgresql_using="gin")
    op.create_index("source_items_url", "source_items", ["workspace_id", "normalized_url"])
    op.create_index("source_items_hash", "source_items", ["workspace_id", "content_hash"])
    op.create_index(
        "source_items_title_trgm",
        "source_items",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_index("source_items_duplicate", "source_items", ["duplicate_of"])

    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("exclusions", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("languages", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("source_ids", postgresql.ARRAY(sa.Uuid()), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("workspace_id", "name", name="topics_name_unique"),
    )
    op.create_table(
        "topic_matches",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id", sa.Uuid(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("source_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("contributions", postgresql.JSONB(), nullable=False),
        sa.Column(
            "matched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("topic_id", "item_id"),
    )
    op.create_index("topic_matches_item", "topic_matches", ["item_id"])
    op.create_index(
        "source_items_unwatched",
        "source_items",
        ["collected_at"],
        postgresql_where=sa.text("watched_at IS NULL AND text_status <> 'pending'"),
    )
    statements = [
        # The owner exception lets unwatched_items, and it alone, read every workspace.
        f"DROP POLICY {rls.POLICY} ON source_items",
        f"CREATE POLICY {rls.POLICY} ON source_items"
        f" USING ({IN_WORKSPACE} OR {rls.AS_OWNER}) WITH CHECK ({IN_WORKSPACE})",
        *rls.workspace_scoped("topics"),
        *rls.workspace_scoped("topic_matches"),
        # The items the watch has not handled yet, in every workspace: an ITEM_READY job lost
        # or failed, or items collected before this migration. Only the catch-up job calls it.
        """
        CREATE FUNCTION unwatched_items(p_limit integer, p_older_than interval)
        RETURNS TABLE (workspace_id uuid, item_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
        AS $$
            SELECT workspace_id, id FROM source_items
            WHERE watched_at IS NULL AND text_status <> 'pending'
              AND collected_at < now() - p_older_than
            ORDER BY collected_at LIMIT p_limit
        $$
        """,
        rls.grant_to_app(UNWATCHED),
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {UNWATCHED}")
    op.execute(f"DROP POLICY {rls.POLICY} ON source_items")
    op.execute(
        f"CREATE POLICY {rls.POLICY} ON source_items USING ({IN_WORKSPACE})"
        f" WITH CHECK ({IN_WORKSPACE})"
    )
    op.drop_table("topic_matches")
    op.drop_table("topics")
    for index in (
        "source_items_unwatched",
        "source_items_duplicate",
        "source_items_title_trgm",
        "source_items_hash",
        "source_items_url",
        "source_items_search",
    ):
        op.drop_index(index, table_name="source_items")
    for column in (
        "search",
        "duplicate_of",
        "watched_at",
        "content_hash",
        "search_config",
        "language",
    ):
        op.drop_column("source_items", column)
