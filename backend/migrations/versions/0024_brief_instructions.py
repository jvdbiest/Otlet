# SPDX-License-Identifier: AGPL-3.0-or-later
"""The writing instructions of a brief (decision of Joël, 2026-10-17): the angle says what the
author wants to say; the instructions say how the draft is written, and reach the model as
instructions, under the rules of the product.

Revision: 0024
Previous: 0023
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("briefs", sa.Column("instructions", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("briefs", "instructions")
