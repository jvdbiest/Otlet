# SPDX-License-Identifier: AGPL-3.0-or-later
"""The archive of the triage, and the items removed for good (decision of Joël, 2026-10-17).

- `item_triage.decision` may be `archived`: the flow of an item is to sort, kept, (drafting,
  from I2), archived. Archived items leave the current views and stay searchable.
- Removing an item, an exceptional action of its page, deletes it with its text, its matches
  and its triage. For an item of a feed, `removed_items` keeps its source, its guid and its
  normalized address only: the next collection of the feed skips it.

Revision: 0015
Previous: 0014
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


DECISIONS = "decision IS NULL OR decision IN ('kept', 'dismissed'{})"


def upgrade() -> None:
    op.drop_constraint("item_triage_decision", "item_triage", type_="check")
    op.create_check_constraint(
        "item_triage_decision", "item_triage", DECISIONS.format(", 'archived'")
    )
    op.create_table(
        "removed_items",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("guid", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=True),
        sa.Column(
            "removed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("source_id", "guid"),
        # The source is in the same workspace (M-12, migration 0008); removing the source
        # removes its traces.
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_id"],
            ["sources.workspace_id", "sources.id"],
            name="removed_items_source_same_workspace",
            ondelete="CASCADE",
        ),
    )
    op.create_index("removed_items_url", "removed_items", ["source_id", "normalized_url"])
    for statement in rls.workspace_scoped("removed_items"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("removed_items")
    # The owner is bound by forced row-level security too, and has no workspace here.
    op.execute("ALTER TABLE item_triage NO FORCE ROW LEVEL SECURITY")
    op.execute("UPDATE item_triage SET decision = 'kept' WHERE decision = 'archived'")
    op.execute("ALTER TABLE item_triage FORCE ROW LEVEL SECURITY")
    op.drop_constraint("item_triage_decision", "item_triage", type_="check")
    op.create_check_constraint("item_triage_decision", "item_triage", DECISIONS.format(""))
