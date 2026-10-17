# SPDX-License-Identifier: AGPL-3.0-or-later
"""The context window of a provider (decision of Joël, 2026-10-17), and drafts written past it.

- `ai_providers.context_window`: null for automatic (the window of each model from the
  catalogue; 4,096 for a local engine), or the window the user set: a local engine's depends on
  its machine.
- `article_versions.context_overflow`: the call used more tokens than the window, so a local
  engine may have dropped the start of the conversation, where the rules of Otlet are.

Revision: 0026
Previous: 0025
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_providers", sa.Column("context_window", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ai_providers_context_window",
        "ai_providers",
        "context_window IS NULL OR context_window BETWEEN 2048 AND 2000000",
    )
    op.add_column(
        "article_versions",
        sa.Column("context_overflow", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("article_versions", "context_overflow")
    op.drop_column("ai_providers", "context_window")
