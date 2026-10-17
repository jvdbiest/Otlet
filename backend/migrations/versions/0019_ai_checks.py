# SPDX-License-Identifier: AGPL-3.0-or-later
"""Checks of a user's AI profile (F05): « Tester » asks the worker for one small structured
answer through the gateway, and the interface reads the result here.

Revision: 0019
Previous: 0018
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from otlet.platform import rls

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_checks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("result", postgresql.JSONB(), nullable=True),  # null while it runs
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    for statement in rls.enable("ai_checks", f"user_id = {rls.CURRENT_USER_ID}"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("ai_checks")
