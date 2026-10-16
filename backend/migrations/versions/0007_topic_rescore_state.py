# SPDX-License-Identifier: AGPL-3.0-or-later
"""When a topic was last asked to be matched again, and up to which request it was (U02b): the
interface tells "recalculation in progress" from "recalculated at…".

Revision: 0007
Previous: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column(
            "rescore_requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column("topics", sa.Column("rescored_at", sa.DateTime(timezone=True), nullable=True))
    # Topics created before this revision were matched already.
    op.execute("UPDATE topics SET rescored_at = rescore_requested_at")


def downgrade() -> None:
    op.drop_column("topics", "rescored_at")
    op.drop_column("topics", "rescore_requested_at")
