# SPDX-License-Identifier: AGPL-3.0-or-later
"""Items the user removed, and the trace that keeps the collection from bringing them back.

Removing an item deletes it with its text, its matches and its triage. For an item of a feed,
`removed_items` keeps its source, its guid and its normalized address only: the next collection
of the feed skips it instead of collecting it again.

Revision: 0014
Previous: 0013
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
