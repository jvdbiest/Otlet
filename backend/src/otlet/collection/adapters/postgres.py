# SPDX-License-Identifier: AGPL-3.0-or-later
"""The collection store on PostgreSQL. Every query runs in the context of its workspace, so
row-level security filters what a query would forget; only `claim_due_sources` crosses
workspaces, through the owner function of the same name (migration 0005)."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from otlet.collection.application.collection import COLLECT_SOURCE, EXTRACT_ITEM, ITEM_READY
from otlet.collection.application.ports import (
    CollectionState,
    NewItem,
    Outcome,
    SitePolicy,
)
from otlet.collection.domain import model
from otlet.collection.domain.compliance import Robots, RobotsKind, TdmRule
from otlet.collection.domain.model import (
    Check,
    CollectionError,
    Decision,
    Item,
    LegalStatus,
    Origin,
    Source,
    TextStatus,
)
from otlet.jobs.application.registry import Enqueue
from otlet.platform.database import scoped_transaction, workspace_transaction
from otlet.platform.rls import here

SOURCE_COLUMNS = (
    "s.id, s.workspace_id, s.name, s.url, s.feed_url, s.site_url, s.interval_minutes, s.active,"
    " s.legal_status, s.legal_reason, s.created_at, s.last_fetched_at, s.last_success_at,"
    " s.last_error, s.consecutive_failures, s.next_fetch_at,"
    f" (SELECT count(*) FROM source_items AS i WHERE i.source_id = s.id AND {here('i')})"
    " AS item_count"
)
ITEM_COLUMNS = (
    "i.id, i.workspace_id, i.source_id, s.name AS source_name, i.origin, i.url, i.title,"
    " i.author, i.published_at, i.collected_at, i.summary,"
    # Only a text Otlet may use is shown: a reserved item keeps its summary alone.
    " CASE WHEN i.text_status IN ('full_text', 'manual')"
    "   THEN coalesce(i.text, i.feed_content) END AS text, i.text_status, i.text_reason,"
    " i.declared_origin, i.usage_right,"
    # Other items of the same story, found by the watch (U02).
    f" (SELECT count(*) FROM source_items AS d WHERE d.duplicate_of = i.id AND {here('d')})"
    " AS duplicate_count"
)
ITEMS_FROM = "source_items AS i LEFT JOIN sources AS s ON s.id = i.source_id"
# Items are listed by publication date, never later than their collection: a feed cannot push
# its items to the top with a date in the future.
SORT_DATE = "least(coalesce(i.published_at, i.collected_at), i.collected_at)"


def _source(row: sa.Row[Any]) -> Source:
    return Source(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        url=row.url,
        feed_url=row.feed_url,
        site_url=row.site_url,
        interval_minutes=row.interval_minutes,
        active=row.active,
        legal_status=LegalStatus(row.legal_status),
        legal_reason=row.legal_reason,
        created_at=row.created_at,
        last_fetched_at=row.last_fetched_at,
        last_success_at=row.last_success_at,
        last_error=row.last_error,
        consecutive_failures=row.consecutive_failures,
        next_fetch_at=row.next_fetch_at,
        item_count=row.item_count,
    )


def item_from_row(row: sa.Row[Any]) -> Item:
    return Item(
        id=row.id,
        workspace_id=row.workspace_id,
        source_id=row.source_id,
        source_name=row.source_name,
        origin=Origin(row.origin),
        url=row.url,
        title=row.title,
        author=row.author,
        published_at=row.published_at,
        collected_at=row.collected_at,
        summary=row.summary,
        text=row.text,
        text_status=TextStatus(row.text_status),
        text_reason=row.text_reason,
        declared_origin=row.declared_origin,
        usage_right=row.usage_right,
        duplicates=row.duplicate_count,
    )


class PostgresCollectionStore:
    def __init__(self, engine: sa.Engine, enqueue: Enqueue) -> None:
        self._engine = engine
        self._enqueue = enqueue

    # Sources ---------------------------------------------------------------------------------

    def add_source(
        self,
        workspace_id: UUID,
        *,
        name: str,
        url: str,
        feed_url: str,
        site_url: str | None,
        interval_minutes: int,
    ) -> Source:
        with workspace_transaction(self._engine, workspace_id) as connection:
            source_id = connection.execute(
                sa.text(
                    "INSERT INTO sources"
                    " (workspace_id, name, url, feed_url, site_url, interval_minutes)"
                    " VALUES (:workspace, :name, :url, :feed_url, :site_url, :interval)"
                    " ON CONFLICT (workspace_id, feed_url) DO NOTHING RETURNING id"
                ),
                {
                    "workspace": workspace_id,
                    "name": name,
                    "url": url,
                    "feed_url": feed_url,
                    "site_url": site_url,
                    "interval": interval_minutes,
                },
            ).scalar_one_or_none()
            if source_id is None:
                raise CollectionError("already_followed", "this feed is already followed")
            self._enqueue(
                connection, COLLECT_SOURCE, workspace_id=str(workspace_id), source_id=str(source_id)
            )
            return self._get_source(connection, source_id)

    @staticmethod
    def _get_source(connection: sa.Connection, source_id: UUID) -> Source:
        row = connection.execute(
            sa.text(f"SELECT {SOURCE_COLUMNS} FROM sources AS s WHERE s.id = :id AND {here('s')}"),  # noqa: S608
            {"id": source_id},
        ).one()
        return _source(row)

    def list_sources(self, workspace_id: UUID) -> list[Source]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {SOURCE_COLUMNS} FROM sources AS s"  # noqa: S608
                    f" WHERE {here('s')} ORDER BY lower(s.name), s.id"
                )
            ).all()
        return [_source(row) for row in rows]

    def get_source(self, workspace_id: UUID, source_id: UUID) -> Source | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT {SOURCE_COLUMNS} FROM sources AS s WHERE s.id = :id AND {here('s')}"
                ),  # noqa: S608
                {"id": source_id},
            ).one_or_none()
        return None if row is None else _source(row)

    def update_source(
        self,
        workspace_id: UUID,
        source_id: UUID,
        *,
        name: str | None,
        interval_minutes: int | None,
        active: bool | None,
    ) -> Source | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            updated = connection.execute(
                sa.text(
                    "UPDATE sources SET"
                    " name = coalesce(:name, name),"
                    " interval_minutes = coalesce(:interval, interval_minutes),"
                    " active = coalesce(:active, active),"
                    # A source switched back on is collected at once.
                    " next_fetch_at = CASE WHEN CAST(:active AS boolean) AND NOT active THEN now()"
                    "                 ELSE next_fetch_at END"
                    f" WHERE id = :id AND {here()} RETURNING id"
                ),
                {"id": source_id, "name": name, "interval": interval_minutes, "active": active},
            ).scalar_one_or_none()
            return None if updated is None else self._get_source(connection, source_id)

    def delete_source(self, workspace_id: UUID, source_id: UUID) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            deleted = connection.execute(
                sa.text(f"DELETE FROM sources WHERE id = :id AND {here()} RETURNING id"),
                {"id": source_id},
            ).scalar_one_or_none()
        return deleted is not None

    def request_collection(self, workspace_id: UUID, source_id: UUID) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            found = connection.execute(
                sa.text(f"SELECT id FROM sources WHERE id = :id AND active AND {here()}"),
                {"id": source_id},
            ).scalar_one_or_none()
            if found is None:
                return False
            self._enqueue(
                connection, COLLECT_SOURCE, workspace_id=str(workspace_id), source_id=str(source_id)
            )
        return True

    # Collection runs -------------------------------------------------------------------------

    def claim_due_sources(self, limit: int) -> int:
        with scoped_transaction(self._engine) as connection:
            due = connection.execute(
                sa.text("SELECT workspace_id, source_id FROM claim_due_sources(:limit)"),
                {"limit": limit},
            ).all()
            for row in due:
                self._enqueue(
                    connection,
                    COLLECT_SOURCE,
                    workspace_id=str(row.workspace_id),
                    source_id=str(row.source_id),
                )
        return len(due)

    def collection_state(self, workspace_id: UUID, source_id: UUID) -> CollectionState | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT {SOURCE_COLUMNS}, s.etag, s.last_modified"  # noqa: S608
                    f" FROM sources AS s WHERE s.id = :id AND {here('s')}"
                ),
                {"id": source_id},
            ).one_or_none()
        if row is None:
            return None
        return CollectionState(_source(row), row.etag, row.last_modified)

    def finish_collection(
        self, workspace_id: UUID, source_id: UUID, outcome: Outcome, items: list[NewItem]
    ) -> int:
        with workspace_transaction(self._engine, workspace_id) as connection:
            exists = connection.execute(
                sa.text(
                    "UPDATE sources SET"
                    " last_fetched_at = :at,"
                    " next_fetch_at = :next,"
                    " last_success_at = CASE WHEN :success THEN :at ELSE last_success_at END,"
                    " last_error = :error,"
                    " consecutive_failures = CASE WHEN :success THEN 0"
                    "                        ELSE consecutive_failures + 1 END,"
                    " legal_status = coalesce(:legal_status, legal_status),"
                    " legal_reason = CASE WHEN CAST(:legal_status AS text) IS NULL"
                    "                THEN legal_reason ELSE :legal_reason END,"
                    " etag = CASE WHEN :success THEN :etag ELSE etag END,"
                    " last_modified = CASE WHEN :success THEN :modified ELSE last_modified END,"
                    " site_url = coalesce(:site_url, site_url)"
                    f" WHERE id = :id AND {here()} RETURNING id"
                ),
                {
                    "id": source_id,
                    "at": outcome.fetched_at,
                    "next": outcome.next_fetch_at,
                    "success": outcome.success,
                    "error": outcome.error,
                    "legal_status": outcome.legal_status and outcome.legal_status.value,
                    "legal_reason": outcome.legal_reason,
                    "etag": outcome.etag,
                    "modified": outcome.last_modified,
                    "site_url": outcome.site_url,
                },
            ).scalar_one_or_none()
            if exists is None:  # deleted during the run
                return 0
            new = 0
            for item in items:
                item_id = self._insert_entry(connection, workspace_id, source_id, item)
                if item_id is None:
                    continue
                new += 1
                # A pending item is read first; the others are ready for the watch at once.
                self._enqueue(
                    connection,
                    EXTRACT_ITEM if item.text_status is TextStatus.PENDING else ITEM_READY,
                    workspace_id=str(workspace_id),
                    item_id=str(item_id),
                )
        return new

    @staticmethod
    def _insert_entry(
        connection: sa.Connection, workspace_id: UUID, source_id: UUID, item: NewItem
    ) -> UUID | None:
        entry = item.entry
        normalized = None if entry.url is None else model.normalize_url(entry.url)
        if (
            normalized is not None
            and connection.execute(
                # The same article under another guid (feeds that renumber) is not new either.
                sa.text(
                    f"SELECT 1 FROM source_items WHERE source_id = :source AND {here()}"
                    " AND normalized_url = :normalized"
                ),
                {"source": source_id, "normalized": normalized},
            ).first()
        ):
            return None
        result: UUID | None = connection.execute(
            sa.text(
                "INSERT INTO source_items (workspace_id, source_id, origin, guid, url,"
                " normalized_url, title, author, published_at, summary, feed_content,"
                " text_status, text_reason, language, search_config)"
                " VALUES (:workspace, :source, 'feed', :guid, :url, :normalized, :title, :author,"
                " :published, :summary, :content, :status, :reason, :language,"
                " CAST(:config AS regconfig))"
                " ON CONFLICT (source_id, guid) DO NOTHING RETURNING id"
            ),
            {
                "workspace": workspace_id,
                "source": source_id,
                "guid": entry.guid,
                "url": entry.url,
                "normalized": normalized,
                "title": entry.title,
                "author": entry.author,
                "published": entry.published_at,
                "summary": entry.summary,
                "content": entry.content,
                "status": item.text_status.value,
                "reason": item.text_reason,
                "language": entry.language,
                "config": model.search_config(entry.language),
            },
        ).scalar_one_or_none()
        return result

    def record_check(
        self, workspace_id: UUID, source_id: UUID | None, url: str, decision: Decision
    ) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO source_checks (workspace_id, source_id, url, allowed, reason,"
                    " detail) VALUES (:workspace, :source, :url, :allowed, :reason, :detail)"
                ),
                {
                    "workspace": workspace_id,
                    "source": source_id,
                    "url": url,
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                    "detail": decision.detail,
                },
            )

    def list_checks(self, workspace_id: UUID, source_id: UUID, limit: int) -> list[Check]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT checked_at, url, allowed, reason, detail FROM source_checks"
                    f" WHERE source_id = :source AND {here()}"
                    " ORDER BY checked_at DESC, id DESC LIMIT :limit"
                ),
                {"source": source_id, "limit": limit},
            ).all()
        return [Check(r.checked_at, r.url, r.allowed, r.reason, r.detail) for r in rows]

    # Items ----------------------------------------------------------------------------------

    def list_items(
        self, workspace_id: UUID, *, source_id: UUID | None, before: UUID | None, limit: int
    ) -> list[Item]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {ITEM_COLUMNS} FROM {ITEMS_FROM}"  # noqa: S608
                    # Without a source filter, a story shows once: its copies are counted.
                    f" WHERE {here('i')} AND (CASE WHEN CAST(:source AS uuid) IS NULL"
                    "   THEN i.duplicate_of IS NULL"
                    "        ELSE i.source_id = :source END)"
                    # Keyset paging on (date, id): items of one run may share their date.
                    f" AND (CAST(:before AS uuid) IS NULL OR ({SORT_DATE}, i.id) <"
                    f"   (SELECT {SORT_DATE}, i.id FROM source_items AS i"
                    f"    WHERE i.id = :before AND {here('i')}))"
                    f" ORDER BY {SORT_DATE} DESC, i.id DESC LIMIT :limit"
                ),
                {"source": source_id, "before": before, "limit": limit},
            ).all()
        return [item_from_row(row) for row in rows]

    def get_item(self, workspace_id: UUID, item_id: UUID) -> Item | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT {ITEM_COLUMNS} FROM {ITEMS_FROM} WHERE i.id = :id AND {here('i')}"
                ),  # noqa: S608
                {"id": item_id},
            ).one_or_none()
        return None if row is None else item_from_row(row)

    def pending_item_url(self, workspace_id: UUID, item_id: UUID) -> str | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            url: str | None = connection.execute(
                sa.text(
                    "SELECT url FROM source_items"
                    f" WHERE id = :id AND text_status = 'pending' AND url IS NOT NULL AND {here()}"
                ),
                {"id": item_id},
            ).scalar_one_or_none()
        return url

    def set_item_text(
        self,
        workspace_id: UUID,
        item_id: UUID,
        *,
        status: TextStatus,
        reason: str,
        text: str | None,
        title: str | None,
        language: str | None,
        at: datetime,
    ) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            updated = connection.execute(
                sa.text(
                    "UPDATE source_items SET text_status = :status, text_reason = :reason,"
                    " text = :text, extracted_at = :at,"
                    # The language of the feed wins; the page tells it when the feed does not.
                    " language = coalesce(language, CAST(:language AS text)),"
                    # A manual URL has no title until its page is read.
                    " title = CASE WHEN origin = 'manual_url' AND CAST(:title AS text) IS NOT NULL"
                    "         THEN :title ELSE title END"
                    f" WHERE id = :id AND text_status = 'pending' AND {here()} RETURNING language"
                ),
                {
                    "id": item_id,
                    "status": status.value,
                    "reason": reason,
                    "text": text,
                    "title": title,
                    "language": language,
                    "at": at,
                },
            ).one_or_none()
            if updated is None:
                return
            connection.execute(
                sa.text(
                    "UPDATE source_items SET search_config = CAST(:config AS regconfig)"
                    f" WHERE id = :id AND {here()}"
                ),
                {"id": item_id, "config": model.search_config(updated.language)},
            )
            self._enqueue(
                connection, ITEM_READY, workspace_id=str(workspace_id), item_id=str(item_id)
            )

    def add_manual_url(self, workspace_id: UUID, url: str, at: datetime) -> Item:
        with workspace_transaction(self._engine, workspace_id) as connection:
            item_id = connection.execute(
                sa.text(
                    "INSERT INTO source_items (workspace_id, origin, url, normalized_url, title,"
                    " collected_at, text_status)"
                    " VALUES (:workspace, 'manual_url', :url, :normalized, :url, :at, 'pending')"
                    " RETURNING id"
                ),
                {
                    "workspace": workspace_id,
                    "url": url,
                    "normalized": model.normalize_url(url),
                    "at": at,
                },
            ).scalar_one()
            self._enqueue(
                connection, EXTRACT_ITEM, workspace_id=str(workspace_id), item_id=str(item_id)
            )
            return self._get_item(connection, item_id)

    def add_manual_text(
        self,
        workspace_id: UUID,
        *,
        title: str,
        text: str,
        url: str | None,
        declared_origin: str,
        usage_right: str,
        at: datetime,
    ) -> Item:
        with workspace_transaction(self._engine, workspace_id) as connection:
            item_id = connection.execute(
                sa.text(
                    "INSERT INTO source_items (workspace_id, origin, url, normalized_url, title,"
                    " collected_at, text, text_status, text_reason, declared_origin,"
                    " usage_right)"
                    " VALUES (:workspace, 'manual_text', :url, :normalized, :title, :at, :text,"
                    " 'manual', 'declared_by_user', :origin, :right) RETURNING id"
                ),
                {
                    "workspace": workspace_id,
                    "url": url,
                    "normalized": None if url is None else model.normalize_url(url),
                    "title": title,
                    "at": at,
                    "text": text,
                    "origin": declared_origin,
                    "right": usage_right,
                },
            ).scalar_one()
            self._enqueue(
                connection, ITEM_READY, workspace_id=str(workspace_id), item_id=str(item_id)
            )
            return self._get_item(connection, item_id)

    @staticmethod
    def _get_item(connection: sa.Connection, item_id: UUID) -> Item:
        row = connection.execute(
            sa.text(f"SELECT {ITEM_COLUMNS} FROM {ITEMS_FROM} WHERE i.id = :id AND {here('i')}"),  # noqa: S608
            {"id": item_id},
        ).one()
        return item_from_row(row)

    # Site rules -------------------------------------------------------------------------------

    def site_policy(self, workspace_id: UUID, origin: str) -> SitePolicy | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "SELECT robots_kind, robots_body, tdm_rules, expires_at FROM site_policies"
                    f" WHERE origin = :origin AND {here()}"
                ),
                {"origin": origin},
            ).one_or_none()
        if row is None:
            return None
        rules = row.tdm_rules if isinstance(row.tdm_rules, list) else json.loads(row.tdm_rules)
        return SitePolicy(
            robots=Robots(RobotsKind(row.robots_kind), row.robots_body),
            tdm_rules=tuple(TdmRule(r["location"], r["reserved"], r.get("policy")) for r in rules),
            expires_at=row.expires_at,
        )

    def save_site_policy(self, workspace_id: UUID, origin: str, policy: SitePolicy) -> None:
        rules = [
            {"location": rule.location, "reserved": rule.reserved, "policy": rule.policy}
            for rule in policy.tdm_rules
        ]
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO site_policies"
                    " (workspace_id, origin, robots_kind, robots_body, tdm_rules, expires_at)"
                    " VALUES (:workspace, :origin, :kind, :body, CAST(:rules AS json), :expires)"
                    " ON CONFLICT (workspace_id, origin) DO UPDATE SET"
                    " robots_kind = excluded.robots_kind, robots_body = excluded.robots_body,"
                    " tdm_rules = excluded.tdm_rules, expires_at = excluded.expires_at"
                ),
                {
                    "workspace": workspace_id,
                    "origin": origin,
                    "kind": policy.robots.kind.value,
                    "body": policy.robots.body,
                    "rules": json.dumps(rules),
                    "expires": policy.expires_at,
                },
            )
