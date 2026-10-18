# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Library (X04, ADR-0037): an article enters it by « Envoyer en Bibliothèque », which validates
a version. An article gets a status, the number of its validated version, the time it was sent,
its tags; a version keeps its plain text, which the search reads.

Revision: 0030
Previous: 0029
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "articles", sa.Column("status", sa.Text(), nullable=False, server_default="brouillon")
    )
    op.create_check_constraint(
        "articles_status", "articles", "status IN ('brouillon', 'valide', 'archive')"
    )
    op.add_column("articles", sa.Column("validated_version", sa.Integer(), nullable=True))
    op.add_column("articles", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "articles",
        sa.Column(
            "tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")
        ),
    )
    op.create_index("articles_library", "articles", ["workspace_id", "sent_at"])
    op.create_index("articles_tags", "articles", ["tags"], postgresql_using="gin")
    op.add_column(
        "article_versions",
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
    )
    # The text of the versions already written: every « text » of their documents, in order.
    op.execute(
        "UPDATE article_versions SET body_text = coalesce((SELECT string_agg(t #>> '{}', ' ')"
        " FROM jsonb_path_query(document, 'strict $.**.text') AS t), '')"
    )


def downgrade() -> None:
    op.drop_column("article_versions", "body_text")
    op.drop_index("articles_tags", table_name="articles")
    op.drop_index("articles_library", table_name="articles")
    op.drop_column("articles", "tags")
    op.drop_column("articles", "sent_at")
    op.drop_column("articles", "validated_version")
    op.drop_constraint("articles_status", "articles")
    op.drop_column("articles", "status")
