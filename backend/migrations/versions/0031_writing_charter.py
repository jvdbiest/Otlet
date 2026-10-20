# SPDX-License-Identifier: AGPL-3.0-or-later
"""The writing charter of each user (Joël, 2026-10-19): standing instructions added to every
draft. No row: the default charter; an empty text: none.

Revision: 0031
Previous: 0030
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "writing_charters",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("charter", sa.Text(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(charter) <= 8000", name="writing_charters_length"),
    )
    for statement in rls.enable("writing_charters", f"user_id = {rls.CURRENT_USER_ID}"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("writing_charters")
