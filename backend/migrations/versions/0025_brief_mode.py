# SPDX-License-Identifier: AGPL-3.0-or-later
"""The mode of a brief (decision of Joël, 2026-10-17): « synthesis », one line of reasoning
across the sources (the default), or « panorama », the sources one after the other.

Revision: 0025
Previous: 0024
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "briefs", sa.Column("mode", sa.Text(), nullable=False, server_default="synthesis")
    )
    op.create_check_constraint("briefs_mode", "briefs", "mode IN ('synthesis', 'panorama')")


def downgrade() -> None:
    op.drop_column("briefs", "mode")
