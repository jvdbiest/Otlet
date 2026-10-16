# SPDX-License-Identifier: AGPL-3.0-or-later
"""Topics, scores, duplicates and search (U02).

An item is scored when the collection announces it ready (ITEM_READY): it is compared with
the earlier items of the workspace to find whether it repeats one of them, then matched with
every topic. A topic created or changed is matched again with the recent items.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from otlet.collection.application.collection import ITEM_READY as ITEM_READY
from otlet.collection.domain.model import Item
from otlet.watch.domain import model
from otlet.watch.domain.model import Candidate, Match, Rules, Topic, WatchError
from otlet.watch.domain.triage import Triage
from otlet.workspaces.domain.model import WorkspaceContext

# Jobs of the module (otlet.watch.adapters.jobs); the collection enqueues ITEM_READY.
RESCORE_TOPIC = "watch.rescore_topic"
CATCH_UP = "watch.catch_up"
# Items the watch has not handled after this delay are handled again, this many per run.
CATCH_UP_AFTER = timedelta(minutes=5)
CATCH_UP_BATCH = 500
# A changed topic is matched again with the items of this period, at most this many.
RESCORE_WINDOW = timedelta(days=30)
RESCORE_MAX_ITEMS = 5000
# A text this short is not fingerprinted: two different news briefs can share it.
FINGERPRINT_MIN_LENGTH = 200
SEARCH_MAX_LENGTH = 200


@dataclass(frozen=True, slots=True)
class ScoredItem:
    item: Item
    score: int  # lexical score plus freshness
    freshness: int
    contributions: tuple[model.Contribution, ...]
    triage: Triage = Triage()


@dataclass(frozen=True, slots=True)
class ItemTopic:
    topic_id: UUID
    name: str
    score: int
    contributions: tuple[model.Contribution, ...]


@dataclass(frozen=True, slots=True)
class Duplicate:
    item_id: UUID
    title: str
    source_name: str | None
    url: str | None


@dataclass(frozen=True, slots=True)
class FoundItem:
    item: Item
    rank: float


@dataclass(frozen=True, slots=True)
class TopicFields:
    name: str
    description: str
    keywords: tuple[str, ...]
    exclusions: tuple[str, ...]
    languages: tuple[str, ...]
    source_ids: tuple[UUID, ...]


class WatchStore(Protocol):
    def list_topics(self, workspace_id: UUID) -> list[Topic]: ...
    def get_topic(self, workspace_id: UUID, topic_id: UUID) -> Topic | None: ...

    def create_topic(self, workspace_id: UUID, fields: TopicFields) -> Topic:
        """Creates the topic and enqueues its first matching (RESCORE_TOPIC)."""
        ...

    def update_topic(self, workspace_id: UUID, topic_id: UUID, fields: TopicFields) -> Topic | None:
        """Changes the topic and enqueues its matching again (RESCORE_TOPIC)."""
        ...

    def delete_topic(self, workspace_id: UUID, topic_id: UUID) -> bool: ...

    def topic_items(
        self,
        workspace_id: UUID,
        topic_id: UUID,
        now: datetime,
        limit: int,
        offset: int,
        user_id: UUID,
    ) -> list[ScoredItem]: ...

    def item_topics(self, workspace_id: UUID, item_id: UUID) -> list[ItemTopic]: ...
    def duplicates(self, workspace_id: UUID, item_id: UUID) -> list[Duplicate]: ...

    def candidate(self, workspace_id: UUID, item_id: UUID) -> Candidate | None: ...

    def mark_duplicate(self, workspace_id: UUID, item_id: UUID, content_hash: bytes | None) -> None:
        """Records the fingerprint of the item and the earlier item it repeats, if any: same
        address, same text, or nearly the same title within two days, from another source."""
        ...

    def save_item_matches(
        self, workspace_id: UUID, item_id: UUID, matches: dict[UUID, Match]
    ) -> None: ...

    def recent_candidates(
        self, workspace_id: UUID, since: datetime, limit: int
    ) -> list[tuple[UUID, Candidate]]: ...

    def save_topic_matches(
        self,
        workspace_id: UUID,
        topic_id: UUID,
        matches: dict[UUID, Match],
        answered: datetime | None,
    ) -> None:
        """Replaces the matches of the topic; they answer the request made at `answered`."""
        ...

    def request_rescore(self, workspace_id: UUID, topic_id: UUID) -> bool: ...
    def refresh(self, workspace_id: UUID) -> tuple[int, int]: ...

    def search(self, workspace_id: UUID, query: str, limit: int) -> list[FoundItem]: ...

    def enqueue_unwatched(self, limit: int, older_than: timedelta) -> int:
        """Enqueues ITEM_READY for the items of every workspace the watch has not handled."""
        ...


def fingerprint(text: str) -> bytes | None:
    words = model.tokens(text)
    if sum(len(word) for word in words) < FINGERPRINT_MIN_LENGTH:
        return None
    return hashlib.sha256(" ".join(words).encode()).digest()


class Watch:
    def __init__(self, store: WatchStore) -> None:
        self._store = store

    # Topics ----------------------------------------------------------------------------------

    @staticmethod
    def _fields(
        *,
        name: str,
        description: str,
        keywords: list[str],
        exclusions: list[str],
        languages: list[str],
        source_ids: list[UUID],
    ) -> TopicFields:
        return TopicFields(
            name=model.check_name(name),
            description=model.check_description(description),
            keywords=model.check_terms(keywords, required=True),
            exclusions=model.check_terms(exclusions, required=False),
            languages=model.check_languages(languages),
            source_ids=tuple(dict.fromkeys(source_ids)),
        )

    def list_topics(self, context: WorkspaceContext) -> list[Topic]:
        return self._store.list_topics(context.workspace_id)

    def get_topic(self, context: WorkspaceContext, topic_id: UUID) -> Topic | None:
        return self._store.get_topic(context.workspace_id, topic_id)

    def create_topic(
        self,
        context: WorkspaceContext,
        *,
        name: str,
        description: str = "",
        keywords: list[str],
        exclusions: list[str] | None = None,
        languages: list[str] | None = None,
        source_ids: list[UUID] | None = None,
    ) -> Topic:
        fields = self._fields(
            name=name,
            description=description,
            keywords=keywords,
            exclusions=exclusions or [],
            languages=languages or [],
            source_ids=source_ids or [],
        )
        return self._store.create_topic(context.workspace_id, fields)

    def update_topic(
        self,
        context: WorkspaceContext,
        topic_id: UUID,
        *,
        name: str,
        description: str = "",
        keywords: list[str],
        exclusions: list[str] | None = None,
        languages: list[str] | None = None,
        source_ids: list[UUID] | None = None,
    ) -> Topic | None:
        fields = self._fields(
            name=name,
            description=description,
            keywords=keywords,
            exclusions=exclusions or [],
            languages=languages or [],
            source_ids=source_ids or [],
        )
        return self._store.update_topic(context.workspace_id, topic_id, fields)

    def delete_topic(self, context: WorkspaceContext, topic_id: UUID) -> bool:
        return self._store.delete_topic(context.workspace_id, topic_id)

    def topic_items(
        self, context: WorkspaceContext, topic_id: UUID, now: datetime, *, limit: int, offset: int
    ) -> list[ScoredItem]:
        return self._store.topic_items(
            context.workspace_id, topic_id, now, min(limit, 200), max(offset, 0), context.user_id
        )

    def item_topics(self, context: WorkspaceContext, item_id: UUID) -> list[ItemTopic]:
        return self._store.item_topics(context.workspace_id, item_id)

    def duplicates(self, context: WorkspaceContext, item_id: UUID) -> list[Duplicate]:
        return self._store.duplicates(context.workspace_id, item_id)

    def rescore(self, context: WorkspaceContext, topic_id: UUID) -> bool:
        """Matches the topic again, on request (the button « Recalculer »)."""
        return self._store.request_rescore(context.workspace_id, topic_id)

    def refresh(self, context: WorkspaceContext) -> tuple[int, int]:
        """Collects every active source now and matches every topic again (« Actualiser »):
        returns how many sources and topics."""
        return self._store.refresh(context.workspace_id)

    def search(self, context: WorkspaceContext, query: str, limit: int = 50) -> list[FoundItem]:
        """Full-text search with a bounded ranking (ADR-0021)."""
        cleaned = " ".join(query.split())
        if not 1 <= len(cleaned) <= SEARCH_MAX_LENGTH:
            raise WatchError("invalid_query", f"a search has 1 to {SEARCH_MAX_LENGTH} characters")
        return self._store.search(context.workspace_id, cleaned, min(limit, 100))

    # Background runs ------------------------------------------------------------------------

    def item_ready(self, workspace_id: UUID, item_id: UUID) -> None:
        """Duplicates, then topics, of an item the collection has finished (job ITEM_READY)."""
        candidate = self._store.candidate(workspace_id, item_id)
        if candidate is None:
            return
        self._store.mark_duplicate(workspace_id, item_id, fingerprint(candidate.text))
        matches = {}
        for topic in self._store.list_topics(workspace_id):
            found = Rules.of(topic).match(candidate)
            if found is not None:
                matches[topic.id] = found
        self._store.save_item_matches(workspace_id, item_id, matches)

    def catch_up(self) -> int:
        """Handles again the items whose ITEM_READY was lost or failed (job CATCH_UP)."""
        return self._store.enqueue_unwatched(CATCH_UP_BATCH, CATCH_UP_AFTER)

    def rescore_topic(self, workspace_id: UUID, topic_id: UUID, now: datetime) -> None:
        """Matches a created or changed topic with the recent items (job RESCORE_TOPIC)."""
        topic = self._store.get_topic(workspace_id, topic_id)
        if topic is None:
            return
        rules = Rules.of(topic)
        matches = {}
        recent = self._store.recent_candidates(
            workspace_id, now - RESCORE_WINDOW, RESCORE_MAX_ITEMS
        )
        for item_id, candidate in recent:
            found = rules.match(candidate)
            if found is not None:
                matches[item_id] = found
        self._store.save_topic_matches(workspace_id, topic_id, matches, topic.rescore_requested_at)
