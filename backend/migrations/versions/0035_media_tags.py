# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tags on the images of the médiathèque (ADR-0040, lot 2): free, like those of the articles,
searched in Médias and in the picker of the editor.

Revision: 0035
Previous: 0034
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "media",
        sa.Column(
            "tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")
        ),
    )
    op.create_index("media_tags", "media", ["tags"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("media_tags", "media")
    op.drop_column("media", "tags")
