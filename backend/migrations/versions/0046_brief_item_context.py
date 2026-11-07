# SPDX-License-Identifier: AGPL-3.0-or-later
"""P2 (docs/design/MATIERE_DU_BRIEF.md): an item of a brief is its matter, or only its context.

Revision: 0046
Previous: 0045
"""

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Context helps to understand the answer without being one: one sentence at most in the
    # draft, never a section (Joël, 2026-11-07). Every existing item stays matter.
    op.add_column(
        "brief_items",
        sa.Column("context", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("brief_items", "context")
