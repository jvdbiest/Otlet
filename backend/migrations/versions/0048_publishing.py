# SPDX-License-Identifier: AGPL-3.0-or-later
"""U07 (docs/design/PUBLICATION_WORDPRESS.md): sending an article to a WordPress site, as a draft
or published, from Otlet.

- `publishing_sites`: the WordPress sites of a workspace, with the application password sealed by
  the public key of the instance (only the worker opens it, DR6), the result of the last « Tester »
  and the categories and tags the site offers, read by that test.
- `publications`: one row per article and site: the WordPress post it became, its status there,
  the version of Otlet it holds, and the state of the last send.
- `publication_events`: the journal of every send (who, when, which version, what the site said).

Revision: 0048
Previous: 0047
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from otlet.platform import rls

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def _now(name: str) -> sa.Column[object]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "publishing_sites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False, server_default="wordpress"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_sealed", sa.LargeBinary(), nullable=False),
        sa.Column("password_hint", sa.Text(), nullable=False),
        # The last « Tester »: ok, or the reason it failed; the role of the account; when.
        sa.Column("check_result", sa.Text(), nullable=True),
        sa.Column("check_detail", sa.Text(), nullable=True),
        sa.Column("check_role", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
        # [{"id": 3, "name": "Sport"}, …] as the site gave them at the last test.
        sa.Column("categories", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        _now("created_at"),
        sa.UniqueConstraint("workspace_id", "id", name="publishing_sites_workspace_id_id_key"),
        sa.UniqueConstraint("workspace_id", "name", name="publishing_sites_one_name"),
        sa.CheckConstraint("kind IN ('wordpress')", name="publishing_sites_kind"),
    )
    op.create_table(
        "publications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        # The key of ADR-0026, written in the slug and in an HTML comment of the post.
        sa.Column("marker", sa.Text(), nullable=False),
        sa.Column("remote_id", sa.BigInteger(), nullable=True),
        sa.Column("remote_status", sa.Text(), nullable=True),
        sa.Column("remote_url", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        # The send under way or the last one: what was asked, and how it went.
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("asked_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "categories",
            postgresql.ARRAY(sa.BigInteger()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")
        ),
        _now("created_at"),
        _now("updated_at"),
        sa.UniqueConstraint("article_id", "site_id", name="publications_one_per_site"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "article_id"],
            ["articles.workspace_id", "articles.id"],
            name="publications_article_same_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "site_id"],
            ["publishing_sites.workspace_id", "publishing_sites.id"],
            name="publications_site_same_workspace",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("action IN ('draft', 'publish')", name="publications_action"),
        sa.CheckConstraint(
            "state IN ('pending', 'done', 'failed', 'to_check')", name="publications_state"
        ),
        sa.CheckConstraint(
            "remote_status IS NULL OR remote_status IN ('draft', 'publish', 'pending',"
            " 'private', 'future', 'trash')",
            name="publications_remote_status",
        ),
    )
    op.create_table(
        "publication_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "publication_id",
            sa.Uuid(),
            sa.ForeignKey("publications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        _now("at"),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("remote_id", sa.BigInteger(), nullable=True),
        sa.Column("remote_status", sa.Text(), nullable=True),
    )
    op.create_index("publication_events_by_publication", "publication_events", ["publication_id"])
    for table in ("publishing_sites", "publications", "publication_events"):
        for statement in rls.workspace_scoped(table):
            op.execute(statement)


def downgrade() -> None:
    op.drop_table("publication_events")
    op.drop_table("publications")
    op.drop_table("publishing_sites")
