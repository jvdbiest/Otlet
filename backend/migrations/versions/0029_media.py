# SPDX-License-Identifier: AGPL-3.0-or-later
"""Images imported into articles (X03b, ADR-0036 §6): their files live in the file storage under
their SHA-256; this table describes them, in the context of each workspace.

Revision: 0029
Previous: 0028
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("mime IN ('image/jpeg', 'image/png', 'image/webp')", name="media_mime"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="media_sha256"),
    )
    op.create_index("media_workspace", "media", ["workspace_id", "created_at"])
    for statement in rls.workspace_scoped("media"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("media")
