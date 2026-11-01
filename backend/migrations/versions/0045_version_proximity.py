# SPDX-License-Identifier: AGPL-3.0-or-later
"""U05 (ADR-0046): how close a version is to its sources, and the author's justification.

Revision: 0045
Previous: 0044
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("article_versions", sa.Column("proximity", postgresql.JSONB(), nullable=True))
    op.add_column(
        "article_versions", sa.Column("proximity_override", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("article_versions", "proximity_override")
    op.drop_column("article_versions", "proximity")
