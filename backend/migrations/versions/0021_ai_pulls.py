# SPDX-License-Identifier: AGPL-3.0-or-later
"""Model installations on a local engine (F05b): a user asks their Ollama to download a model;
the worker follows the download and writes its progress here, the interface reads it.

Revision: 0021
Previous: 0020
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_pulls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("step", sa.Text(), nullable=False, server_default=""),
        sa.Column("completed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('running', 'done', 'failed')", name="ai_pulls_status"),
        # The provider is one of the user's; removing it removes its installations.
        sa.ForeignKeyConstraint(
            ["user_id", "provider_id"],
            ["ai_providers.user_id", "ai_providers.id"],
            name="ai_pulls_provider_of_user",
            ondelete="CASCADE",
        ),
    )
    for statement in rls.enable("ai_pulls", f"user_id = {rls.CURRENT_USER_ID}"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("ai_pulls")
