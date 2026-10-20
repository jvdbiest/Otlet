# SPDX-License-Identifier: AGPL-3.0-or-later
"""Declarations of rights (Joël, 2026-10-20): on an item whose publisher reserves text mining,
a person declares holding the rights needed (an agreement of the publisher, a licence, their own
content, another basis they name), and Otlet reads the page under their responsibility. Each
declaration is kept: who, when, which item, on what basis, the exact words of the commitment;
it can be withdrawn, never erased.

Revision: 0032
Previous: 0031
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rights_declarations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "declared_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("commitment", sa.Text(), nullable=False),
        # The reason the text was out of reach, given back when the declaration is withdrawn.
        sa.Column("previous_reason", sa.Text(), nullable=False),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "item_id"],
            ["source_items.workspace_id", "source_items.id"],
            name="rights_declarations_item_same_workspace",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "basis IN ('publisher_agreement', 'licence', 'own_content', 'other')",
            name="rights_declarations_basis",
        ),
        sa.CheckConstraint(
            "basis <> 'other' OR length(btrim(detail)) > 0", name="rights_declarations_other"
        ),
    )
    op.create_index("rights_declarations_item", "rights_declarations", ["workspace_id", "item_id"])
    for statement in rls.workspace_scoped("rights_declarations"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("rights_declarations")
