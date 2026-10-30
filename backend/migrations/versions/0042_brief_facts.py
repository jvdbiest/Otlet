# SPDX-License-Identifier: AGPL-3.0-or-later
"""The verified facts of a brief (ADR-0044 §10, A2-3): the lines of a fact of the Reporter, with
their source and passage, and the conversation they come from.

Revision: 0042
Previous: 0041
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "briefs",
        sa.Column(
            "facts", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
    )
    op.add_column(
        "briefs",
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("reporter_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("briefs", "conversation_id")
    op.drop_column("briefs", "facts")
