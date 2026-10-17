# SPDX-License-Identifier: AGPL-3.0-or-later
"""The details of a generation (Joël, 2026-10-17): what a draft was written with, to diagnose it
without guessing: the settings of the brief, the window and the room left for the sources, what
each source sent, and why Otlet refused an answer. Never the text of the prompt nor the answer.

Revision: 0027
Previous: 0026
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "article_generations",
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("article_generations", "details")
