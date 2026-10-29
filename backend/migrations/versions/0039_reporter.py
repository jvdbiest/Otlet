# SPDX-License-Identifier: AGPL-3.0-or-later
"""The conversations of the Reporter (ADR-0044): each question, the operation it became, the
concepts and language of the set, the items found, the lines of fact and their agreement, with
the model and the version of its prompt. They let the author come back to a conversation and
see where each answer comes from.

Revision: 0039
Previous: 0038
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from otlet.platform import rls

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

EMPTY_LIST = sa.text("'[]'::jsonb")
EMPTY_OBJECT = sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "reporter_conversations",
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
        sa.Column("days", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 200", name="reporter_conversations_title"),
    )
    op.create_index(
        "reporter_conversations_recent",
        "reporter_conversations",
        ["workspace_id", "created_by", sa.text("created_at DESC")],
    )
    op.create_table(
        "reporter_turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("reporter_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("operation", sa.Text(), nullable=True),
        # The state after the turn (concepts as asked, language), the concepts as searched
        # (widened, general terms, counts), the set, the fact, the verdicts of a sort.
        sa.Column("state", postgresql.JSONB(), nullable=False, server_default=EMPTY_OBJECT),
        sa.Column("concepts", postgresql.JSONB(), nullable=False, server_default=EMPTY_LIST),
        sa.Column("candidates", postgresql.JSONB(), nullable=False, server_default=EMPTY_LIST),
        sa.Column("fact", postgresql.JSONB(), nullable=True),
        sa.Column("verdicts", postgresql.JSONB(), nullable=False, server_default=EMPTY_OBJECT),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("attempts", postgresql.JSONB(), nullable=False, server_default=EMPTY_LIST),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("conversation_id", "position", name="reporter_turns_position"),
        sa.CheckConstraint("status IN ('pending', 'done', 'failed')", name="reporter_turns_status"),
        sa.CheckConstraint("length(question) BETWEEN 1 AND 500", name="reporter_turns_question"),
    )
    for table in ("reporter_conversations", "reporter_turns"):
        for statement in rls.workspace_scoped(table):
            op.execute(statement)


def downgrade() -> None:
    op.drop_table("reporter_turns")
    op.drop_table("reporter_conversations")
