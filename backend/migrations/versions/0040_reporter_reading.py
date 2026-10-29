# SPDX-License-Identifier: AGPL-3.0-or-later
"""« Vérifier en lisant » (Joël, 2026-10-29): the set of a question read by the model, asked or
done — the items read in each round, those that truly answer and why, and what is missing.

Revision: 0040
Previous: 0039
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reporter_turns", sa.Column("reading", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("reporter_turns", "reading")
