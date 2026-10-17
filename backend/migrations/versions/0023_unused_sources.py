# SPDX-License-Identifier: AGPL-3.0-or-later
"""The items of a brief a draft leaves out (U04, Joël's case of 2026-10-17): every source must
be cited; a draft that still leaves one out after a repair is kept and says which.

Revision: 0023
Previous: 0022
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "article_versions",
        sa.Column("unused_sources", postgresql.JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("article_versions", "unused_sources")
