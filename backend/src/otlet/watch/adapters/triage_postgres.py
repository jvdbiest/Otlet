# SPDX-License-Identifier: AGPL-3.0-or-later
"""The feed and its triage on PostgreSQL, in the context of each workspace."""

from typing import Any
from uuid import UUID

import sqlalchemy as sa

from otlet.collection.adapters.postgres import ITEM_COLUMNS, ITEMS_FROM, SORT_DATE, item_from_row
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here
from otlet.watch.application.triage import Change, FeedItem
from otlet.watch.domain.triage import (
    ANY_TIME,
    NO_TOPIC_FILTER,
    Decision,
    Period,
    Progress,
    TopicFilter,
    TopicTag,
    Triage,
    View,
)

TRIAGE_COLUMNS = "tr.decision, coalesce(tr.pinned, false) AS pinned, tr.read_at"
TRIAGE_JOIN = (
    " LEFT JOIN item_triage AS tr ON tr.item_id = i.id AND tr.user_id = :user"
    " AND tr.workspace_id = i.workspace_id"
)
VIEWS = {
    View.TO_SORT: "tr.decision IS NULL",
    View.KEPT: "tr.decision = 'kept'",
    View.DISMISSED: "tr.decision = 'dismissed'",
    View.PINNED: "coalesce(tr.pinned, false)",
    View.ALL: "true",
}
# The topic filter of the feed and of the search; no topic chosen means no filter.
TOPICS = (
    " AND (cardinality(CAST(:topics AS uuid[])) = 0 OR (SELECT count(DISTINCT m.topic_id)"
    "   FROM topic_matches AS m WHERE m.item_id = i.id AND m.workspace_id = i.workspace_id"
    "   AND m.topic_id = ANY(CAST(:topics AS uuid[])))"
    "  >= CASE WHEN CAST(:all_topics AS boolean) THEN cardinality(CAST(:topics AS uuid[]))"
    "     ELSE 1 END)"
)


def topic_parameters(topics: TopicFilter) -> dict[str, object]:
    return {"topics": list(topics.topic_ids), "all_topics": topics.all_topics}


def period_clause(date: str) -> str:
    """The period filter of the feed and of the search, on the date expression given."""
    return (
        f" AND (CAST(:since AS timestamptz) IS NULL OR {date} >= CAST(:since AS timestamptz))"
        f" AND (CAST(:until AS timestamptz) IS NULL OR {date} < CAST(:until AS timestamptz))"
    )


def period_parameters(period: Period) -> dict[str, object]:
    return {"since": period.since, "until": period.until}


# The topics of each item, best score first (the first is its main topic).
TOPIC_TAGS = (
    "(SELECT coalesce(json_agg(json_build_object('id', t.id, 'name', t.name, 'score', m.score)"
    "  ORDER BY m.score DESC, t.name), '[]') FROM topic_matches AS m"
    " JOIN topics AS t ON t.id = m.topic_id AND t.workspace_id = m.workspace_id"
    " WHERE m.item_id = i.id AND m.workspace_id = i.workspace_id) AS topic_tags"
)


def topic_tags_of(row: sa.Row[Any]) -> tuple[TopicTag, ...]:
    return tuple(
        TopicTag(id=UUID(tag["id"]), name=tag["name"], score=tag["score"]) for tag in row.topic_tags
    )


# Pinned items first, then the most recent; the cursor follows the same order.
ORDER_KEY = f"(CASE WHEN coalesce(tr.pinned, false) THEN 1 ELSE 0 END), {SORT_DATE}, i.id"


def triage_of(row: sa.Row[Any]) -> Triage:
    return Triage(
        decision=None if row.decision is None else Decision(row.decision),
        pinned=row.pinned,
        read_at=row.read_at,
    )


class PostgresTriageStore:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def feed(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        view: View,
        source_id: UUID | None,
        unread_only: bool,
        before: UUID | None,
        limit: int,
        topics: TopicFilter = NO_TOPIC_FILTER,
        period: Period = ANY_TIME,
    ) -> list[FeedItem]:
        # 'Tout' is in date order only; the other views put the pinned items first.
        order_key = f"{SORT_DATE}, i.id" if view is View.ALL else ORDER_KEY
        order_by = (
            f"{SORT_DATE} DESC, i.id DESC"
            if view is View.ALL
            else f"coalesce(tr.pinned, false) DESC, {SORT_DATE} DESC, i.id DESC"
        )
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {ITEM_COLUMNS}, {TRIAGE_COLUMNS}, {TOPIC_TAGS}"
                    f" FROM {ITEMS_FROM}{TRIAGE_JOIN}"
                    f" WHERE {here('i')} AND {VIEWS[view]}"
                    # Without a source filter, a story shows once: its copies are counted.
                    " AND (CASE WHEN CAST(:source AS uuid) IS NULL THEN i.duplicate_of IS NULL"
                    "      ELSE i.source_id = :source END)"
                    " AND (NOT CAST(:unread AS boolean) OR tr.read_at IS NULL)"
                    f"{TOPICS}{period_clause(SORT_DATE)}"
                    f" AND (CAST(:before AS uuid) IS NULL OR ({order_key}) < ("
                    f"   SELECT {order_key} FROM source_items AS i{TRIAGE_JOIN}"
                    f"   WHERE i.id = :before AND {here('i')}))"
                    f" ORDER BY {order_by} LIMIT :limit"
                ),
                {
                    "user": user_id,
                    "source": source_id,
                    "unread": unread_only,
                    "before": before,
                    "limit": limit,
                    **topic_parameters(topics),
                    **period_parameters(period),
                },
            ).all()
        return [FeedItem(item_from_row(row), triage_of(row), topic_tags_of(row)) for row in rows]

    def triage(self, workspace_id: UUID, user_id: UUID, item_id: UUID) -> Triage | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            return self._triage(connection, user_id, item_id)

    @staticmethod
    def _triage(connection: sa.Connection, user_id: UUID, item_id: UUID) -> Triage | None:
        row = connection.execute(
            sa.text(
                f"SELECT {TRIAGE_COLUMNS} FROM source_items AS i{TRIAGE_JOIN}"
                f" WHERE i.id = :item AND {here('i')}"
            ),
            {"user": user_id, "item": item_id},
        ).one_or_none()
        return None if row is None else triage_of(row)

    def change(
        self, workspace_id: UUID, user_id: UUID, item_id: UUID, change: Change
    ) -> Triage | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            if self._triage(connection, user_id, item_id) is None:
                return None
            self._apply(connection, workspace_id, user_id, item_id, change)
            return self._triage(connection, user_id, item_id)

    def change_many(
        self, workspace_id: UUID, user_id: UUID, item_ids: list[UUID], change: Change
    ) -> int:
        with workspace_transaction(self._engine, workspace_id) as connection:
            found = (
                connection.execute(
                    sa.text(f"SELECT id FROM source_items WHERE id = ANY(:ids) AND {here()}"),
                    {"ids": item_ids},
                )
                .scalars()
                .all()
            )
            for item_id in found:
                self._apply(connection, workspace_id, user_id, item_id, change)
        return len(found)

    @staticmethod
    def _apply(
        connection: sa.Connection, workspace_id: UUID, user_id: UUID, item_id: UUID, change: Change
    ) -> None:
        decision = None if change.decision is None else change.decision.value
        connection.execute(
            sa.text(
                "INSERT INTO item_triage (workspace_id, item_id, user_id, decision, pinned,"
                " read_at, decided_at)"
                " VALUES (:workspace, :item, :user, CAST(:decision AS text),"
                " coalesce(CAST(:pinned AS boolean), false),"
                " CASE WHEN CAST(:read AS boolean) THEN now() END,"
                " CASE WHEN CAST(:decision AS text) IS NOT NULL THEN now() END)"
                " ON CONFLICT (item_id, user_id) DO UPDATE SET"
                " decision = CASE WHEN CAST(:clear AS boolean) THEN NULL"
                "   ELSE coalesce(CAST(:decision AS text), item_triage.decision) END,"
                " decided_at = CASE WHEN CAST(:clear AS boolean)"
                "   OR CAST(:decision AS text) IS NOT NULL THEN now()"
                "   ELSE item_triage.decided_at END,"
                " pinned = coalesce(CAST(:pinned AS boolean), item_triage.pinned),"
                " read_at = CASE WHEN CAST(:read AS boolean) IS NULL THEN item_triage.read_at"
                "   WHEN CAST(:read AS boolean) THEN coalesce(item_triage.read_at, now())"
                "   END"
            ),
            {
                "workspace": workspace_id,
                "item": item_id,
                "user": user_id,
                "decision": decision,
                "clear": change.clear_decision,
                "pinned": change.pinned,
                "read": change.read,
            },
        )

    def progress(self, workspace_id: UUID, user_id: UUID) -> Progress:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT (SELECT count(*) FROM sources WHERE {here()}) AS sources,"
                    f" (SELECT count(*) FROM topics WHERE {here()}) AS topics,"
                    " (SELECT count(*) FROM item_triage WHERE user_id = :user"
                    f"  AND decision IS NOT NULL AND {here()}) AS decisions"
                ),
                {"user": user_id},
            ).one()
        return Progress(sources=row.sources, topics=row.topics, decisions=row.decisions)
