# SPDX-License-Identifier: AGPL-3.0-or-later
"""« Reconstituer » (ADR-0044 §7): the reconstitution of an answer, asked or done.

Revision: 0044
Previous: 0043
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reporter_turns", sa.Column("reconstitution", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("reporter_turns", "reconstitution")
