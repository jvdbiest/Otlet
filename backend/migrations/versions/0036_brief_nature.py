# SPDX-License-Identifier: AGPL-3.0-or-later
"""The nature of a brief (ADR-0041): « news » (Actualité, the default and the value of the
briefs made before) or « background » (Dossier de fond). It only changes how the matter of
the brief is judged.

Revision: 0036
Previous: 0035
"""

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("briefs", sa.Column("nature", sa.Text(), nullable=False, server_default="news"))
    op.create_check_constraint("briefs_nature", "briefs", "nature IN ('news', 'background')")


def downgrade() -> None:
    op.drop_column("briefs", "nature")
