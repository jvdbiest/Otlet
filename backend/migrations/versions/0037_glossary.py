# SPDX-License-Identifier: AGPL-3.0-or-later
"""The glossary of a workspace (ADR-0043): terms that mean the same thing, in one or several
languages (« Bruxelles-Capitale », « Brussels Hoofdstedelijk Gewest »). The Assistant de veille
widens a subject with it, without a model; the topics and A1a may use it later.

Revision: 0037
Previous: 0036
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from otlet.platform import rls

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "glossary_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("terms", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("cardinality(terms) BETWEEN 2 AND 30", name="glossary_entries_terms"),
    )
    op.create_index("glossary_entries_workspace", "glossary_entries", ["workspace_id"])
    for statement in rls.workspace_scoped("glossary_entries"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("glossary_entries")
