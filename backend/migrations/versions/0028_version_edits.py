# SPDX-License-Identifier: AGPL-3.0-or-later
"""Versions retouched in the editor (X03, ADR-0036): « Enregistrer » updates a person's version
in place, so a version gets the time of its last change, and the version it was made from.

Revision: 0028
Previous: 0027
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "article_versions",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.execute("UPDATE article_versions SET updated_at = created_at")
    op.add_column("article_versions", sa.Column("based_on", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("article_versions", "based_on")
    op.drop_column("article_versions", "updated_at")
