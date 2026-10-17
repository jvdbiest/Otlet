# SPDX-License-Identifier: AGPL-3.0-or-later
"""The monthly AI budget of each user, with reservation (F05, ADR-0027 §3).

- `ai_budget_limits`: the monthly limit the user chose (0 by default: free models only).
- `ai_budget_months`: for each month, the limit in force, what was spent and what is reserved
  by calls in progress. A call reserves by one conditional update of this row.

Both belong to a user, under row-level security.

Revision: 0017
Previous: 0016
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

OWN = f"user_id = {rls.CURRENT_USER_ID}"


def upgrade() -> None:
    op.create_table(
        "ai_budget_limits",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("monthly_limit", sa.Numeric(), nullable=False, server_default="0"),
        sa.CheckConstraint("monthly_limit >= 0", name="ai_budget_limits_positive"),
    )
    op.create_table(
        "ai_budget_months",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("budget_limit", sa.Numeric(), nullable=False),
        sa.Column("spent", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Numeric(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("user_id", "month"),
        sa.CheckConstraint("spent >= 0 AND reserved >= 0", name="ai_budget_months_positive"),
    )
    for table in ("ai_budget_limits", "ai_budget_months"):
        for statement in rls.enable(table, OWN):
            op.execute(statement)


def downgrade() -> None:
    op.drop_table("ai_budget_months")
    op.drop_table("ai_budget_limits")
