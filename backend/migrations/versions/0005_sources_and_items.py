# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sources, collected items, the compliance journal and the cache of site rules (U01).

- `sources`: the feeds a workspace follows, their legal status (M-08), health and schedule.
- `source_items`: what the sources brought, or what the user entered by hand, with the status
  of its text and, for a pasted text, the declared origin and right of use.
- `source_checks`: the compliance journal (CJ-03): when and why a source was allowed,
  reduced to summaries or refused.
- `site_policies`: robots.txt and tdmrep.json per origin, cached for a day.

All four are workspace data under forced row-level security. `claim_due_sources`, owned by the
schema owner, is the only way to see the sources of every workspace: the worker calls it to
find the sources that are due, then works on each one in its own workspace context. The owner
exception of the `sources` policy is true only inside that function (ADR-0028).

Revision: 0005
Previous: 0004
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

CLAIM = "claim_due_sources(integer)"
DEFINER = "SECURITY DEFINER SET search_path = pg_catalog, public"
NOW = {"nullable": False, "server_default": sa.func.now()}


def _id() -> sa.Column[object]:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("uuidv7()"))


def _workspace() -> sa.Column[object]:
    return sa.Column(
        "workspace_id",
        sa.Uuid(),
        sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "sources",
        _id(),
        _workspace(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("feed_url", sa.Text(), nullable=False),
        sa.Column("site_url", sa.Text(), nullable=True),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("legal_status", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("legal_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), **NOW),
        sa.Column("next_fetch_at", sa.DateTime(timezone=True), **NOW),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.UniqueConstraint("workspace_id", "feed_url", name="sources_feed_url_unique"),
        sa.CheckConstraint(
            "legal_status IN ('unknown', 'full_text', 'summary_only', 'refused')",
            name="sources_legal_status",
        ),
        sa.CheckConstraint("interval_minutes BETWEEN 15 AND 10080", name="sources_interval"),
    )
    op.create_index("sources_due", "sources", ["next_fetch_at"], postgresql_where=sa.text("active"))
    op.create_table(
        "source_items",
        _id(),
        _workspace(),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("guid", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("normalized_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), **NOW),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("feed_content", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("text_status", sa.Text(), nullable=False),
        sa.Column("text_reason", sa.Text(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declared_origin", sa.Text(), nullable=True),
        sa.Column("usage_right", sa.Text(), nullable=True),
        sa.UniqueConstraint("source_id", "guid", name="source_items_guid_unique"),
        sa.CheckConstraint(
            "origin IN ('feed', 'manual_url', 'manual_text')", name="source_items_origin"
        ),
        sa.CheckConstraint(
            "text_status IN ('pending', 'full_text', 'summary_only', 'manual')",
            name="source_items_text_status",
        ),
        # A pasted text always carries its declaration (M-08).
        sa.CheckConstraint(
            "origin <> 'manual_text' OR (declared_origin IS NOT NULL AND usage_right IS NOT NULL)",
            name="source_items_manual_declared",
        ),
        sa.CheckConstraint(
            "(origin = 'feed') = (source_id IS NOT NULL AND guid IS NOT NULL)",
            name="source_items_feed_has_source",
        ),
    )
    op.create_index(
        "source_items_recent", "source_items", ["workspace_id", sa.text("collected_at DESC")]
    )
    op.create_index("source_items_source", "source_items", ["source_id"])
    op.create_table(
        "source_checks",
        _id(),
        _workspace(),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), **NOW),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("source_checks_source", "source_checks", ["source_id", "checked_at"])
    op.create_table(
        "site_policies",
        _workspace(),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("robots_kind", sa.Text(), nullable=False),
        sa.Column("robots_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("tdm_rules", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "origin"),
    )

    in_workspace = f"workspace_id = {rls.CURRENT_WORKSPACE}"
    statements = [
        *rls.enable("sources", using=f"{in_workspace} OR {rls.AS_OWNER}"),
        *rls.workspace_scoped("source_items"),
        *rls.workspace_scoped("source_checks"),
        *rls.workspace_scoped("site_policies"),
        f"""
        CREATE FUNCTION claim_due_sources(p_limit integer)
        RETURNS TABLE (workspace_id uuid, source_id uuid)
        LANGUAGE sql {DEFINER}
        AS $$
            UPDATE sources AS s
            SET next_fetch_at = now() + make_interval(mins => s.interval_minutes)
            FROM (SELECT id FROM sources
                  WHERE active AND next_fetch_at <= now()
                  ORDER BY next_fetch_at
                  LIMIT p_limit
                  FOR UPDATE SKIP LOCKED) AS due
            WHERE s.id = due.id
            RETURNING s.workspace_id, s.id
        $$
        """,  # noqa: S608 (constant DEFINER clause)
        rls.grant_to_app(CLAIM),
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {CLAIM}")
    for table in ("site_policies", "source_checks", "source_items", "sources"):
        op.drop_table(table)
