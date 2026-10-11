# SPDX-License-Identifier: AGPL-3.0-or-later
"""Throw-away migration of the S6 upgrade scenario (C2): plays the role of version N+1.
Never copied into backend/migrations.

Revision: 0002
Previous: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instance_settings", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("instance_settings", "note")
