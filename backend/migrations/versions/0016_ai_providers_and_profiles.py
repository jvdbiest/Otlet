# SPDX-License-Identifier: AGPL-3.0-or-later
"""The AI providers of each user and their ordered profile of models (F05, ADR-0027).

- `ai_providers`: a provider a user declared: its kind (from the catalogue), its address and,
  when the kind needs one, its API key, sealed by the API with the public key of the instance
  (only the worker can open it, DR6). The last characters of the key are kept apart to show
  which key is set.
- `ai_profile_entries`: the models the gateway tries, in order, for this user.

Both belong to a user, not to a workspace: row-level security shows a user their own rows only.

Revision: 0016
Previous: 0015
"""

import sqlalchemy as sa
from alembic import op

from otlet.platform import rls

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

OWN = f"user_id = {rls.CURRENT_USER_ID}"


def upgrade() -> None:
    op.create_table(
        "ai_providers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("api_key_sealed", sa.LargeBinary(), nullable=True),
        sa.Column("key_hint", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "name", name="ai_providers_name_unique"),
        sa.UniqueConstraint("user_id", "id", name="ai_providers_user_id_key"),
    )
    op.create_table(
        "ai_profile_entries",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "position"),
        # The provider belongs to the same user; removing it removes it from the profile.
        sa.ForeignKeyConstraint(
            ["user_id", "provider_id"],
            ["ai_providers.user_id", "ai_providers.id"],
            name="ai_profile_entries_own_provider",
            ondelete="CASCADE",
        ),
    )
    for table in ("ai_providers", "ai_profile_entries"):
        for statement in rls.enable(table, OWN):
            op.execute(statement)


def downgrade() -> None:
    op.drop_table("ai_profile_entries")
    op.drop_table("ai_providers")
