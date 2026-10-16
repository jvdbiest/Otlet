# SPDX-License-Identifier: AGPL-3.0-or-later
"""References that cannot cross workspaces, and the repair of those that did (M-12).

Until the Compose stack connected with otlet_app, the application ran as the superuser of
PostgreSQL, which row-level security does not bind. A refresh then requested the matching of
the topics of every workspace, and wrote some matches under the workspace of whoever asked.

- Repair: rows whose workspace differs from the one of what they reference are removed (matches,
  compliance entries, items) or cut (a duplicate link), and every item is handed again to the
  watch, whose catch-up job rewrites the matches in the right workspace.
- From now on, the workspace is part of each reference: a match, an item, a duplicate link or
  a compliance entry can only point within its own workspace, whatever role writes it.

Revision: 0008
Previous: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TABLES = ("sources", "source_items", "source_checks", "topics", "topic_matches")
PARENT_KEYS = (
    ("sources", "sources_workspace_id_key"),
    ("source_items", "source_items_workspace_id_key"),
    ("topics", "topics_workspace_id_key"),
)
REFERENCES = (
    # table, constraint, columns, parent, parent columns, on delete
    (
        "topic_matches",
        "topic_matches_topic_same_workspace",
        "workspace_id, topic_id",
        "topics",
        "CASCADE",
    ),
    (
        "topic_matches",
        "topic_matches_item_same_workspace",
        "workspace_id, item_id",
        "source_items",
        "CASCADE",
    ),
    (
        "source_items",
        "source_items_source_same_workspace",
        "workspace_id, source_id",
        "sources",
        "CASCADE",
    ),
    (
        "source_items",
        "source_items_duplicate_same_workspace",
        "workspace_id, duplicate_of",
        "source_items",
        "SET NULL (duplicate_of)",
    ),
    (
        "source_checks",
        "source_checks_source_same_workspace",
        "workspace_id, source_id",
        "sources",
        "CASCADE",
    ),
)
REPAIR = (
    "DELETE FROM topic_matches AS m USING topics AS t"
    " WHERE t.id = m.topic_id AND t.workspace_id <> m.workspace_id",
    "DELETE FROM topic_matches AS m USING source_items AS i"
    " WHERE i.id = m.item_id AND i.workspace_id <> m.workspace_id",
    "DELETE FROM source_checks AS c USING sources AS s"
    " WHERE s.id = c.source_id AND s.workspace_id <> c.workspace_id",
    "DELETE FROM source_items AS i USING sources AS s"
    " WHERE s.id = i.source_id AND s.workspace_id <> i.workspace_id",
    "UPDATE source_items AS i SET duplicate_of = NULL FROM source_items AS o"
    " WHERE o.id = i.duplicate_of AND o.workspace_id <> i.workspace_id",
    # The catch-up job of the watch handles these items again (watch.catch_up).
    "UPDATE source_items SET watched_at = NULL WHERE text_status <> 'pending'",
)


def upgrade() -> None:
    # The owner is bound by forced row-level security too, and has no workspace here: the
    # repair needs every row, so forcing is lifted for this transaction only.
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    for statement in REPAIR:
        op.execute(statement)
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    for table, name in PARENT_KEYS:
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} UNIQUE (workspace_id, id)")
    for table, name, columns, parent, on_delete in REFERENCES:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({columns})"
            f" REFERENCES {parent} (workspace_id, id) ON DELETE {on_delete}"
        )


def downgrade() -> None:
    for table, name, *_ in reversed(REFERENCES):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
    for table, name in reversed(PARENT_KEYS):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
