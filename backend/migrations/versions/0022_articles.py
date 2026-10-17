# SPDX-License-Identifier: AGPL-3.0-or-later
"""Articles, their versions and the generations of drafts (U04, F-RED-02, F-RED-04).

- An article is written from a brief: one article per brief. Deleting the brief keeps the
  article, without its brief.
- Each version holds the whole « Document plateforme v1 » (ADR-0023) and says who made it: the
  model (provider, model, version of the prompt) or a person. Versions are never changed.
- A generation is the request of a draft, run by the worker: running, done (with the version it
  made) or failed (with why). Its attempts are kept, never the prompt nor the answer.

Revision: 0022
Previous: 0021
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from otlet.platform import rls

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def _now(name: str) -> sa.Column[object]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "articles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("brief_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.Text(), nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.UniqueConstraint("workspace_id", "id", name="articles_workspace_id_id_key"),
        sa.UniqueConstraint("brief_id", name="articles_one_per_brief"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "brief_id"],
            ["briefs.workspace_id", "briefs.id"],
            name="articles_brief_same_workspace",
            ondelete="SET NULL (brief_id)",
        ),
    )
    op.create_table(
        "article_versions",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("provider_kind", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        # The keys of the sources whose text was cut to fit the model.
        sa.Column("cut_sources", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        _now("created_at"),
        sa.PrimaryKeyConstraint("article_id", "number"),
        sa.CheckConstraint("origin IN ('ia', 'humain')", name="article_versions_origin"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "article_id"],
            ["articles.workspace_id", "articles.id"],
            name="article_versions_article_same_workspace",
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "article_generations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("article_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("attempts", postgresql.JSONB(), nullable=False, server_default="[]"),
        _now("created_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'done', 'failed')", name="article_generations_status"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "brief_id"],
            ["briefs.workspace_id", "briefs.id"],
            name="article_generations_brief_same_workspace",
            ondelete="CASCADE",
        ),
    )
    op.create_index("article_generations_brief", "article_generations", ["brief_id", "created_at"])
    for table in ("articles", "article_versions", "article_generations"):
        for statement in rls.workspace_scoped(table):
            op.execute(statement)


def downgrade() -> None:
    op.drop_table("article_generations")
    op.drop_table("article_versions")
    op.drop_table("articles")
