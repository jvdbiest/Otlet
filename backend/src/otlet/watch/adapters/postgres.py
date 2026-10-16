# SPDX-License-Identifier: AGPL-3.0-or-later
"""The watch store on PostgreSQL, in the context of each workspace (row-level security)."""

import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from otlet.collection.adapters.postgres import ITEM_COLUMNS, ITEMS_FROM, SORT_DATE, item_from_row
from otlet.collection.application.collection import COLLECT_SOURCE
from otlet.collection.domain.model import SEARCH_CONFIGS, SIMPLE_SEARCH
from otlet.jobs.application.registry import Enqueue
from otlet.platform.database import scoped_transaction, workspace_transaction
from otlet.platform.rls import here
from otlet.watch.adapters.triage_postgres import (
    TOPIC_TAGS,
    TOPICS,
    TRIAGE_COLUMNS,
    TRIAGE_JOIN,
    topic_parameters,
    topic_tags_of,
    triage_of,
)
from otlet.watch.application.watch import (
    ITEM_READY,
    RESCORE_TOPIC,
    Duplicate,
    FoundItem,
    ItemTopic,
    ScoredItem,
    TopicFields,
)
from otlet.watch.domain import model
from otlet.watch.domain.model import Candidate, Contribution, Match, Topic, WatchError
from otlet.watch.domain.triage import NO_TOPIC_FILTER, TopicFilter

TOPIC_COLUMNS = (
    "t.id, t.workspace_id, t.name, t.description, t.keywords, t.exclusions, t.languages,"
    " t.source_ids, t.created_at, t.rescore_requested_at, t.rescored_at,"
    " (SELECT count(*) FROM topic_matches AS m JOIN source_items AS i ON i.id = m.item_id"
    f"  WHERE m.topic_id = t.id AND i.duplicate_of IS NULL AND {here('m')}) AS item_count"
)
# Summary, then the text when it may be used: what a topic is matched against.
CANDIDATE_COLUMNS = (
    "i.id, i.title, i.language, i.source_id, concat_ws(E'\\n', i.summary, CASE WHEN"
    " i.text_status IN ('full_text', 'manual') THEN coalesce(i.text, i.feed_content) END)"
    " AS body"
)
# Titles at least this long and this similar, two days apart at most, are the same story.
TITLE_SIMILARITY = 0.9
TITLE_MIN_LENGTH = 20
SAME_STORY_SECONDS = 2 * 24 * 3600
SEARCH_WINDOW = 1000  # candidates ranked by a search (ADR-0021)
CONFIGS = (*dict.fromkeys(SEARCH_CONFIGS.values()), SIMPLE_SEARCH)


def _topic(row: sa.Row[Any]) -> Topic:
    return Topic(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        description=row.description,
        keywords=tuple(row.keywords),
        exclusions=tuple(row.exclusions),
        languages=tuple(row.languages),
        source_ids=tuple(row.source_ids),
        created_at=row.created_at,
        rescore_requested_at=row.rescore_requested_at,
        rescored_at=row.rescored_at,
        item_count=row.item_count,
    )


def _contributions(value: Any) -> tuple[Contribution, ...]:
    data = value if isinstance(value, list) else json.loads(value)
    return tuple(Contribution(c["term"], c["where"], c["count"], c["points"]) for c in data)


def _json(match: Match) -> str:
    return json.dumps(
        [
            {"term": c.term, "where": c.where, "count": c.count, "points": c.points}
            for c in match.contributions
        ],
        ensure_ascii=False,
    )


def _candidate(row: sa.Row[Any]) -> Candidate:
    return Candidate(
        title=row.title, text=row.body or "", language=row.language, source_id=row.source_id
    )


class PostgresWatchStore:
    def __init__(self, engine: sa.Engine, enqueue: Enqueue) -> None:
        self._engine = engine
        self._enqueue = enqueue

    # Topics ---------------------------------------------------------------------------------

    def list_topics(self, workspace_id: UUID) -> list[Topic]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {TOPIC_COLUMNS} FROM topics AS t WHERE {here('t')}"
                    " ORDER BY lower(t.name), t.id"
                )
            ).all()
        return [_topic(row) for row in rows]

    def get_topic(self, workspace_id: UUID, topic_id: UUID) -> Topic | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            return self._get_topic(connection, topic_id)

    @staticmethod
    def _get_topic(connection: sa.Connection, topic_id: UUID) -> Topic | None:
        row = connection.execute(
            sa.text(f"SELECT {TOPIC_COLUMNS} FROM topics AS t WHERE t.id = :id AND {here('t')}"),  # noqa: S608
            {"id": topic_id},
        ).one_or_none()
        return None if row is None else _topic(row)

    @staticmethod
    def _values(fields: TopicFields) -> dict[str, Any]:
        return {
            "name": fields.name,
            "description": fields.description,
            "keywords": list(fields.keywords),
            "exclusions": list(fields.exclusions),
            "languages": list(fields.languages),
            "sources": list(fields.source_ids),
        }

    def _check_sources(self, connection: sa.Connection, fields: TopicFields) -> None:
        if not fields.source_ids:
            return
        known = connection.execute(
            sa.text(f"SELECT count(*) FROM sources WHERE id = ANY(:ids) AND {here()}"),
            {"ids": list(fields.source_ids)},
        ).scalar_one()
        if known != len(fields.source_ids):
            raise WatchError("unknown_source", "a targeted source does not exist")

    def create_topic(self, workspace_id: UUID, fields: TopicFields) -> Topic:
        with workspace_transaction(self._engine, workspace_id) as connection:
            self._check_sources(connection, fields)
            topic_id = connection.execute(
                sa.text(
                    "INSERT INTO topics (workspace_id, name, description, keywords, exclusions,"
                    " languages, source_ids) VALUES (:workspace, :name, :description, :keywords,"
                    " :exclusions, :languages, CAST(:sources AS uuid[]))"
                    " ON CONFLICT (workspace_id, name) DO NOTHING RETURNING id"
                ),
                {"workspace": workspace_id, **self._values(fields)},
            ).scalar_one_or_none()
            if topic_id is None:
                raise WatchError("name_taken", "a topic already has this name")
            self._enqueue(
                connection, RESCORE_TOPIC, workspace_id=str(workspace_id), topic_id=str(topic_id)
            )
            topic = self._get_topic(connection, topic_id)
            if topic is None:  # just inserted in this transaction
                raise LookupError(topic_id)
            return topic

    def update_topic(self, workspace_id: UUID, topic_id: UUID, fields: TopicFields) -> Topic | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            self._check_sources(connection, fields)
            try:
                with connection.begin_nested():
                    updated = connection.execute(
                        sa.text(
                            "UPDATE topics SET name = :name, description = :description,"
                            " keywords = :keywords, exclusions = :exclusions,"
                            " languages = :languages, source_ids = CAST(:sources AS uuid[]),"
                            " updated_at = now(), rescore_requested_at = now()"
                            f" WHERE id = :id AND {here()} RETURNING id"
                        ),
                        {"id": topic_id, **self._values(fields)},
                    ).scalar_one_or_none()
            except sa.exc.IntegrityError as error:
                raise WatchError("name_taken", "a topic already has this name") from error
            if updated is None:
                return None
            self._enqueue(
                connection, RESCORE_TOPIC, workspace_id=str(workspace_id), topic_id=str(topic_id)
            )
            return self._get_topic(connection, topic_id)

    def delete_topic(self, workspace_id: UUID, topic_id: UUID) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            deleted = connection.execute(
                sa.text(f"DELETE FROM topics WHERE id = :id AND {here()} RETURNING id"),
                {"id": topic_id},
            ).scalar_one_or_none()
        return deleted is not None

    # Reading -----------------------------------------------------------------------------------

    def topic_items(
        self,
        workspace_id: UUID,
        topic_id: UUID,
        now: datetime,
        limit: int,
        offset: int,
        user_id: UUID,
    ) -> list[ScoredItem]:
        fresh = " ".join(
            f"WHEN {SORT_DATE} > CAST(:now AS timestamptz) - interval '{int(age.total_seconds())}"
            f" seconds' THEN {points}"
            for age, points in model.FRESH_POINTS
        )
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {ITEM_COLUMNS}, m.score, m.contributions, {TRIAGE_COLUMNS},"
                    f" CASE {fresh} ELSE 0 END AS freshness"
                    f" FROM topic_matches AS m JOIN {ITEMS_FROM} ON i.id = m.item_id{TRIAGE_JOIN}"
                    f" WHERE m.topic_id = :topic AND i.duplicate_of IS NULL AND {here('m')}"
                    # What the user dismissed leaves the topic too.
                    " AND tr.decision IS DISTINCT FROM 'dismissed'"
                    f" ORDER BY m.score + CASE {fresh} ELSE 0 END DESC, {SORT_DATE} DESC, i.id DESC"
                    " LIMIT :limit OFFSET :offset"
                ),
                {"topic": topic_id, "now": now, "limit": limit, "offset": offset, "user": user_id},
            ).all()
        return [
            ScoredItem(
                item=item_from_row(row),
                score=row.score + row.freshness,
                freshness=row.freshness,
                contributions=_contributions(row.contributions),
                triage=triage_of(row),
            )
            for row in rows
        ]

    def item_topics(self, workspace_id: UUID, item_id: UUID) -> list[ItemTopic]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT t.id, t.name, m.score, m.contributions FROM topic_matches AS m"
                    " JOIN topics AS t ON t.id = m.topic_id"
                    f" WHERE m.item_id = :item AND {here('m')}"
                    " ORDER BY m.score DESC, lower(t.name)"
                ),
                {"item": item_id},
            ).all()
        return [
            ItemTopic(row.id, row.name, row.score, _contributions(row.contributions))
            for row in rows
        ]

    def duplicates(self, workspace_id: UUID, item_id: UUID) -> list[Duplicate]:
        """The other items of the same story: the original and its other copies."""
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "WITH root AS (SELECT coalesce(duplicate_of, id) AS id FROM source_items"
                    f" WHERE id = :item AND {here()})"
                    " SELECT i.id, i.title, s.name AS source_name, i.url"
                    " FROM source_items AS i LEFT JOIN sources AS s ON s.id = i.source_id, root"
                    " WHERE (i.id = root.id OR i.duplicate_of = root.id) AND i.id <> :item"
                    f" AND {here('i')}"
                    " ORDER BY i.collected_at, i.id"
                ),
                {"item": item_id},
            ).all()
        return [Duplicate(row.id, row.title, row.source_name, row.url) for row in rows]

    # Scoring --------------------------------------------------------------------------------

    def candidate(self, workspace_id: UUID, item_id: UUID) -> Candidate | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT {CANDIDATE_COLUMNS} FROM source_items AS i"  # noqa: S608
                    f" WHERE i.id = :id AND i.text_status <> 'pending' AND {here('i')}"
                ),
                {"id": item_id},
            ).one_or_none()
        return None if row is None else _candidate(row)

    def mark_duplicate(self, workspace_id: UUID, item_id: UUID, content_hash: bytes | None) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "WITH me AS (SELECT i.id, i.workspace_id, i.source_id, i.normalized_url,"
                    " i.title,"
                    f" i.collected_at, {SORT_DATE} AS day"
                    f" FROM source_items AS i WHERE i.id = :id AND {here('i')}),"
                    " original AS ("
                    "  SELECT coalesce(o.duplicate_of, o.id) AS id"
                    "  FROM source_items AS o, me"
                    "  WHERE o.id <> me.id AND o.workspace_id = me.workspace_id"
                    "  AND (o.collected_at, o.id) < (me.collected_at, me.id)"
                    "  AND o.source_id IS DISTINCT FROM me.source_id"
                    "  AND ((me.normalized_url IS NOT NULL"
                    "        AND o.normalized_url = me.normalized_url)"
                    "   OR (CAST(:hash AS bytea) IS NOT NULL AND o.content_hash = :hash)"
                    "   OR (length(me.title) >= :min_length AND o.title % me.title"
                    "       AND similarity(o.title, me.title) >= :similarity"
                    f"      AND abs(extract(epoch FROM ({SORT_DATE.replace('i.', 'o.')} - me.day)))"
                    "        < :seconds))"
                    "  ORDER BY o.collected_at, o.id LIMIT 1)"
                    " UPDATE source_items SET content_hash = :hash,"
                    f" duplicate_of = (SELECT id FROM original) WHERE id = :id AND {here()}"
                ),
                {
                    "id": item_id,
                    "hash": content_hash,
                    "min_length": TITLE_MIN_LENGTH,
                    "similarity": TITLE_SIMILARITY,
                    "seconds": SAME_STORY_SECONDS,
                },
            )

    def save_item_matches(
        self, workspace_id: UUID, item_id: UUID, matches: dict[UUID, Match]
    ) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(f"DELETE FROM topic_matches WHERE item_id = :item AND {here()}"),
                {"item": item_id},
            )
            connection.execute(
                sa.text(
                    f"UPDATE source_items SET watched_at = now() WHERE id = :item AND {here()}"
                ),
                {"item": item_id},
            )
            self._insert(
                connection,
                workspace_id,
                [(topic_id, item_id, match) for topic_id, match in matches.items()],
            )

    def recent_candidates(
        self, workspace_id: UUID, since: datetime, limit: int
    ) -> list[tuple[UUID, Candidate]]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {CANDIDATE_COLUMNS} FROM source_items AS i"  # noqa: S608
                    " WHERE i.text_status <> 'pending' AND i.collected_at >= :since"
                    f" AND {here('i')}"
                    " ORDER BY i.collected_at DESC, i.id DESC LIMIT :limit"
                ),
                {"since": since, "limit": limit},
            ).all()
        return [(row.id, _candidate(row)) for row in rows]

    def save_topic_matches(
        self,
        workspace_id: UUID,
        topic_id: UUID,
        matches: dict[UUID, Match],
        answered: datetime | None,
    ) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE topics SET rescored_at = greatest(rescored_at, CAST(:answered AS"
                    f" timestamptz)) WHERE id = :topic AND {here()}"
                ),
                {"topic": topic_id, "answered": answered},
            )
            connection.execute(
                sa.text(f"DELETE FROM topic_matches WHERE topic_id = :topic AND {here()}"),
                {"topic": topic_id},
            )
            self._insert(
                connection,
                workspace_id,
                [(topic_id, item_id, match) for item_id, match in matches.items()],
            )

    def request_rescore(self, workspace_id: UUID, topic_id: UUID) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            return self._request(connection, workspace_id, "AND id = :topic", topic_id) > 0

    def refresh(self, workspace_id: UUID) -> tuple[int, int]:
        """Collects every active source now and matches every topic again."""
        with workspace_transaction(self._engine, workspace_id) as connection:
            query = sa.text(f"SELECT id FROM sources WHERE active AND {here()}")
            sources = connection.execute(query).scalars()
            count = 0
            for source_id in sources:
                count += 1
                self._enqueue(
                    connection,
                    COLLECT_SOURCE,
                    workspace_id=str(workspace_id),
                    source_id=str(source_id),
                )
            topics = self._request(connection, workspace_id, "", None)
        return count, topics

    def _request(
        self, connection: sa.Connection, workspace_id: UUID, where: str, topic_id: UUID | None
    ) -> int:
        ids = (
            connection.execute(
                sa.text(
                    f"UPDATE topics SET rescore_requested_at = now() WHERE {here()} {where}"
                    " RETURNING id"
                ),
                {"topic": topic_id},
            )
            .scalars()
            .all()
        )
        for found in ids:
            self._enqueue(
                connection, RESCORE_TOPIC, workspace_id=str(workspace_id), topic_id=str(found)
            )
        return len(ids)

    @staticmethod
    def _insert(
        connection: sa.Connection, workspace_id: UUID, rows: list[tuple[UUID, UUID, Match]]
    ) -> None:
        if not rows:
            return
        connection.execute(
            sa.text(
                "INSERT INTO topic_matches (workspace_id, topic_id, item_id, score, contributions)"
                " VALUES (:workspace, :topic, :item, :score, CAST(:contributions AS jsonb))"
                # The topic may have been deleted meanwhile: nothing to keep then.
                " ON CONFLICT DO NOTHING"
            ),
            [
                {
                    "workspace": workspace_id,
                    "topic": topic_id,
                    "item": item_id,
                    "score": match.score,
                    "contributions": _json(match),
                }
                for topic_id, item_id, match in rows
            ],
        )

    def enqueue_unwatched(self, limit: int, older_than: timedelta) -> int:
        with scoped_transaction(self._engine) as connection:
            rows = connection.execute(
                sa.text("SELECT workspace_id, item_id FROM unwatched_items(:limit, :older)"),
                {"limit": limit, "older": older_than},
            ).all()
            for row in rows:
                self._enqueue(
                    connection,
                    ITEM_READY,
                    workspace_id=str(row.workspace_id),
                    item_id=str(row.item_id),
                )
        return len(rows)

    # Search ---------------------------------------------------------------------------------

    def search(
        self,
        workspace_id: UUID,
        query: str,
        limit: int,
        user_id: UUID | None = None,
        topics: TopicFilter = NO_TOPIC_FILTER,
    ) -> list[FoundItem]:
        """Bounded ranking (ADR-0021): the GIN index and the date keep the 1,000 most recent
        items that match the query, in any language configuration; only those are ranked."""
        matches = " OR ".join(
            f"i.search @@ websearch_to_tsquery('{config}', :q)" for config in CONFIGS
        )
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "WITH found AS ("  # noqa: S608
                    f" SELECT i.id FROM source_items AS i WHERE ({matches}) AND {here('i')}"
                    "  AND i.duplicate_of IS NULL"
                    f"{TOPICS}"
                    f" ORDER BY {SORT_DATE} DESC LIMIT {SEARCH_WINDOW})"
                    f" SELECT {ITEM_COLUMNS}, {TRIAGE_COLUMNS}, {TOPIC_TAGS},"
                    " ts_rank(i.search, websearch_to_tsquery(i.search_config, :q)) AS rank"
                    f" FROM found JOIN {ITEMS_FROM} ON i.id = found.id{TRIAGE_JOIN}"
                    f" ORDER BY rank DESC, {SORT_DATE} DESC, i.id DESC LIMIT :limit"
                ),
                {"q": query, "limit": limit, "user": user_id, **topic_parameters(topics)},
            ).all()
        return [
            FoundItem(item_from_row(row), float(row.rank), triage_of(row), topic_tags_of(row))
            for row in rows
        ]
