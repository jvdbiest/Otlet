# SPDX-License-Identifier: AGPL-3.0-or-later
"""Briefs (U03, F-RED-01): the instructions of an article, built on items the user kept.

- A brief has a working title, the angle and own contribution of its author (M-19), an
  audience, a tone, a length, a language, a target channel, and the model it asks for: the
  profile of its author (no provider), or one provider of its author and one model.
- `brief_items` lists its items, in order, in the same workspace.
- `item_triage.decision` may be `writing`: an item of a brief is in drafting, the step between
  kept and archived of the flow Joël chose (2026-10-17).

Revision: 0020
Previous: 0019
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

DECISIONS = "decision IS NULL OR decision IN ('kept', 'dismissed', 'archived'{})"


def upgrade() -> None:
    op.drop_constraint("item_triage_decision", "item_triage", type_="check")
    op.create_check_constraint(
        "item_triage_decision", "item_triage", DECISIONS.format(", 'writing'")
    )
    op.create_table(
        "briefs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("angle", sa.Text(), nullable=False, server_default=""),
        sa.Column("audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("tone", sa.Text(), nullable=False, server_default=""),
        sa.Column("length", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("language", sa.Text(), nullable=False, server_default="fr"),
        sa.Column("channel", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("workspace_id", "id", name="briefs_workspace_id_id_key"),
        # The chosen provider belongs to the author; removing it falls back to the profile.
        sa.ForeignKeyConstraint(
            ["created_by", "provider_id"],
            ["ai_providers.user_id", "ai_providers.id"],
            name="briefs_provider_of_author",
            ondelete="SET NULL (provider_id)",
        ),
        sa.CheckConstraint("length IN ('short', 'medium', 'long')", name="briefs_length"),
        # A provider comes with a model; a model left without its provider (removed) is ignored.
        sa.CheckConstraint(
            "provider_id IS NULL OR model IS NOT NULL", name="briefs_provider_with_model"
        ),
    )
    op.create_index("briefs_recent", "briefs", ["workspace_id", "updated_at"])
    op.create_table(
        "brief_items",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("brief_id", "item_id"),
        # Both in the same workspace (M-12, migration 0008).
        sa.ForeignKeyConstraint(
            ["workspace_id", "brief_id"],
            ["briefs.workspace_id", "briefs.id"],
            name="brief_items_brief_same_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "item_id"],
            ["source_items.workspace_id", "source_items.id"],
            name="brief_items_item_same_workspace",
            ondelete="CASCADE",
        ),
    )
    op.create_index("brief_items_item", "brief_items", ["workspace_id", "item_id"])
    for table in ("briefs", "brief_items"):
        for statement in rls.workspace_scoped(table):
            op.execute(statement)


def downgrade() -> None:
    op.drop_table("brief_items")
    op.drop_table("briefs")
    # The owner is bound by forced row-level security too, and has no workspace here.
    op.execute("ALTER TABLE item_triage NO FORCE ROW LEVEL SECURITY")
    op.execute("UPDATE item_triage SET decision = 'kept' WHERE decision = 'writing'")
    op.execute("ALTER TABLE item_triage FORCE ROW LEVEL SECURITY")
    op.drop_constraint("item_triage_decision", "item_triage", type_="check")
    op.create_check_constraint("item_triage_decision", "item_triage", DECISIONS.format(""))
