# SPDX-License-Identifier: AGPL-3.0-or-later
"""A declaration of rights may cover a whole source (Joël, 2026-10-20): an agreement of the
publisher or a licence for its site, applied to the articles collected from the declaration
on, until an optional end date. A declaration names an item or a source, never both.

Revision: 0033
Previous: 0032
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("rights_declarations", "item_id", nullable=True)
    op.add_column("rights_declarations", sa.Column("source_id", sa.Uuid(), nullable=True))
    op.add_column("rights_declarations", sa.Column("ends_on", sa.Date(), nullable=True))
    op.create_foreign_key(
        "rights_declarations_source_same_workspace",
        "rights_declarations",
        "sources",
        ["workspace_id", "source_id"],
        ["workspace_id", "id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "rights_declarations_one_target",
        "rights_declarations",
        "(item_id IS NULL) <> (source_id IS NULL)",
    )
    # A whole site is covered by an agreement or a licence only.
    op.create_check_constraint(
        "rights_declarations_source_basis",
        "rights_declarations",
        "source_id IS NULL OR basis IN ('publisher_agreement', 'licence')",
    )
    op.create_index(
        "rights_declarations_source", "rights_declarations", ["workspace_id", "source_id"]
    )


def downgrade() -> None:
    # Declarations of sources cannot be deleted here (row security shows the migration no
    # row): item_id stays nullable, the source ones lose their source.
    op.drop_index("rights_declarations_source", table_name="rights_declarations")
    op.drop_constraint("rights_declarations_source_basis", "rights_declarations")
    op.drop_constraint("rights_declarations_one_target", "rights_declarations")
    op.drop_constraint("rights_declarations_source_same_workspace", "rights_declarations")
    op.drop_column("rights_declarations", "ends_on")
    op.drop_column("rights_declarations", "source_id")
