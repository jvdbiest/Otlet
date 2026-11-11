# SPDX-License-Identifier: AGPL-3.0-or-later
"""The model a user chooses for each writing language (docs/design/MODELE_PAR_LANGUE.md).

- `ai_language_models`: for a language, the provider and model that write the drafts of that
  language when the brief names no model. No row: the user's profile, as before.

It belongs to a user, like the profile: row-level security shows a user their own rows only.

Revision: 0047
Previous: 0046
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

OWN = f"user_id = {rls.CURRENT_USER_ID}"


def upgrade() -> None:
    op.create_table(
        "ai_language_models",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "language"),
        # The provider belongs to the same user; removing it removes the choice, and the
        # language goes back to the profile.
        sa.ForeignKeyConstraint(
            ["user_id", "provider_id"],
            ["ai_providers.user_id", "ai_providers.id"],
            name="ai_language_models_own_provider",
            ondelete="CASCADE",
        ),
    )
    for statement in rls.enable("ai_language_models", OWN):
        op.execute(statement)


def downgrade() -> None:
    op.drop_table("ai_language_models")
