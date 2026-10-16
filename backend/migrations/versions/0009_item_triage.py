# SPDX-License-Identifier: AGPL-3.0-or-later
"""Triage of the watch (X02, F-VEI-05, UC-06): what each user kept, dismissed, pinned or read.

The state belongs to a user, not to the workspace: when a workspace has several editors, each
sorts their own feed. An item without a row is new and unread.

Revision: 0009
Previous: 0008
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_triage",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("item_id", "user_id"),
        # The item is in the same workspace as its triage (M-12, migration 0008).
        sa.ForeignKeyConstraint(
            ["workspace_id", "item_id"],
            ["source_items.workspace_id", "source_items.id"],
            name="item_triage_item_same_workspace",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('kept', 'dismissed')", name="item_triage_decision"
        ),
    )
    op.create_index("item_triage_user", "item_triage", ["workspace_id", "user_id", "decision"])
    for statement in rls.workspace_scoped("item_triage"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("item_triage")
