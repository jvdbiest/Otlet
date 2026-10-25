# SPDX-License-Identifier: AGPL-3.0-or-later
"""The dossiers of the Assistant de veille (ADR-0043 §6): a subject, its concepts and terms, the
items found and what the model said of each, with the model and the version of its prompt.
They let the author come back to a dossier and see why an item was set aside.

Revision: 0038
Previous: 0037
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from otlet.platform import rls

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

EMPTY_LIST = sa.text("'[]'::jsonb")
EMPTY_OBJECT = sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "assistant_dossiers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("angle", sa.Text(), nullable=False, server_default=""),
        sa.Column("days", sa.Integer(), nullable=True),
        # The author's concepts, when given; the concepts used, widened by the glossary.
        sa.Column("requested", postgresql.JSONB(), nullable=False, server_default=EMPTY_LIST),
        sa.Column("concepts", postgresql.JSONB(), nullable=False, server_default=EMPTY_LIST),
        sa.Column("candidates", postgresql.JSONB(), nullable=False, server_default=EMPTY_LIST),
        sa.Column("verdicts", postgresql.JSONB(), nullable=False, server_default=EMPTY_OBJECT),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("attempts", postgresql.JSONB(), nullable=False, server_default=EMPTY_LIST),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'qualifying', 'done')", name="assistant_dossiers_status"
        ),
        sa.CheckConstraint(
            "length(subject) BETWEEN 1 AND 200 AND length(angle) <= 500",
            name="assistant_dossiers_lengths",
        ),
    )
    op.create_index(
        "assistant_dossiers_recent",
        "assistant_dossiers",
        ["workspace_id", "created_by", sa.text("created_at DESC")],
    )
    for statement in rls.workspace_scoped("assistant_dossiers"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("assistant_dossiers")
