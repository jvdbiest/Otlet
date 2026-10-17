# SPDX-License-Identifier: AGPL-3.0-or-later
"""The journal of AI calls of each user (F05, ADR-0027): every attempt of the gateway, with its
result, its tokens, its cost and its duration. Never the prompt nor the answer.

Revision: 0018
Previous: 0017
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("usage", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=True),  # kept when the provider is removed
        sa.Column("provider_kind", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("seconds", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ai_calls_user_at", "ai_calls", ["user_id", "at"])
    for statement in rls.enable("ai_calls", f"user_id = {rls.CURRENT_USER_ID}"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("ai_calls")
