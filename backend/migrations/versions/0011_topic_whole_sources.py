# SPDX-License-Identifier: AGPL-3.0-or-later
"""A topic may take every item of its targeted sources (ADR-0032 §1, request of Joël).

Until now the targeted sources of a topic only limited where its keywords were looked for.
With `whole_sources`, every item of those sources belongs to the topic, and the keywords
become optional: they only add points. Existing topics keep the former rule.

Revision: 0011
Previous: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("whole_sources", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("topics", "whole_sources")
