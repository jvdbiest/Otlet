# SPDX-License-Identifier: AGPL-3.0-or-later
"""The language of the items collected before U02, guessed from their text.

Items collected before migration 0006 have no language, nor do those whose feed and page
declare none. A topic limited to some languages left them out, and their search was not
stemmed. Their language is now guessed from their frequent words (`guess_language`), and
the items whose language is found are handed again to the watch, whose catch-up job matches
them against every topic.

Revision: 0010
Previous: 0009
"""

import sqlalchemy as sa
from alembic import op

from otlet.collection.domain.model import guess_language, search_config

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

BATCH = 500


def upgrade() -> None:
    connection = op.get_bind()
    # The owner is bound by forced row-level security too, and has no workspace here: the
    # repair needs every row, so forcing is lifted for this transaction only.
    op.execute("ALTER TABLE source_items NO FORCE ROW LEVEL SECURITY")
    ids = (
        connection.execute(sa.text("SELECT id FROM source_items WHERE language IS NULL"))
        .scalars()
        .all()
    )
    for start in range(0, len(ids), BATCH):
        rows = connection.execute(
            sa.text(
                "SELECT id, title, summary, coalesce(text, feed_content) AS text"
                " FROM source_items WHERE id = ANY(:ids)"
            ),
            {"ids": list(ids[start : start + BATCH])},
        ).all()
        for row in rows:
            language = guess_language(" ".join(filter(None, (row.title, row.summary, row.text))))
            if language is None:
                continue
            connection.execute(
                sa.text(
                    "UPDATE source_items SET language = :language,"
                    " search_config = CAST(:config AS regconfig),"
                    # The catch-up job of the watch handles the item again (watch.catch_up).
                    " watched_at = CASE WHEN text_status <> 'pending' THEN NULL"
                    "   ELSE watched_at END"
                    " WHERE id = :id"
                ),
                {"id": row.id, "language": language, "config": search_config(language)},
            )
    op.execute("ALTER TABLE source_items FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    # The guessed languages are kept: they are not distinguished from declared ones.
    pass
