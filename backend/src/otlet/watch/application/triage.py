# SPDX-License-Identifier: AGPL-3.0-or-later
"""The watch feed and its triage (X02, F-VEI-04, F-VEI-05, UC-06).

The feed shows each story once (the copies are counted, U02), pinned items first, then the most
recent. Each user sorts it: keep, dismiss, pin, and an item opened is read.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from otlet.collection.domain.model import Item
from otlet.watch.domain.triage import (
    ANY_TIME,
    NO_TOPIC_FILTER,
    Decision,
    Group,
    GroupBy,
    InGroup,
    Period,
    Progress,
    Sort,
    TopicFilter,
    TopicTag,
    Triage,
    View,
)
from otlet.workspaces.domain.model import WorkspaceContext

# « Tout sélectionner » takes every item of the filters, not only the page shown (Joël,
# 2026-10-20): one bulk action takes as many.
SELECTION_MAX = 5000
BULK_MAX = SELECTION_MAX  # items of one bulk action
FEED_MAX = 200


@dataclass(frozen=True, slots=True)
class FeedItem:
    item: Item
    triage: Triage
    topics: tuple[TopicTag, ...] = ()  # best score first


@dataclass(frozen=True, slots=True)
class Change:
    """What a triage request changes; a field left to None is kept as it is."""

    decision: Decision | None = None
    clear_decision: bool = False
    pinned: bool | None = None
    read: bool | None = None


class TriageStore(Protocol):
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
        sort: Sort = Sort.DATE,
        group: InGroup | None = None,
    ) -> list[FeedItem]: ...

    def groups(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        by: GroupBy,
        view: View,
        source_id: UUID | None,
        unread_only: bool,
        topics: TopicFilter = NO_TOPIC_FILTER,
        period: Period = ANY_TIME,
    ) -> list[Group]:
        """The groups of the feed and how many items each shows with these filters."""
        ...

    def ids(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        view: View,
        source_id: UUID | None,
        unread_only: bool,
        topics: TopicFilter = NO_TOPIC_FILTER,
        period: Period = ANY_TIME,
        limit: int,
    ) -> list[UUID]:
        """The ids of the items the feed shows with these filters, every page and group."""
        ...

    def triage(self, workspace_id: UUID, user_id: UUID, item_id: UUID) -> Triage | None:
        """The triage of an item of the workspace (the default for one never sorted), or None
        when the item does not exist."""
        ...

    def change(
        self, workspace_id: UUID, user_id: UUID, item_id: UUID, change: Change
    ) -> Triage | None: ...

    def change_many(
        self, workspace_id: UUID, user_id: UUID, item_ids: list[UUID], change: Change
    ) -> int:
        """Applies a change to the items of the workspace among these; returns how many."""
        ...

    def progress(self, workspace_id: UUID, user_id: UUID) -> Progress: ...


class Feed:
    def __init__(self, store: TriageStore) -> None:
        self._store = store

    def ids(
        self,
        context: WorkspaceContext,
        *,
        view: View = View.TO_SORT,
        source_id: UUID | None = None,
        unread_only: bool = False,
        topics: TopicFilter = NO_TOPIC_FILTER,
        period: Period = ANY_TIME,
    ) -> list[UUID]:
        """« Tout sélectionner »: the ids of every item of the filters, SELECTION_MAX at most."""
        return self._store.ids(
            context.workspace_id,
            context.user_id,
            view=view,
            source_id=source_id,
            unread_only=unread_only,
            topics=topics,
            period=period,
            limit=SELECTION_MAX,
        )

    def feed(
        self,
        context: WorkspaceContext,
        *,
        view: View = View.TO_SORT,
        source_id: UUID | None = None,
        unread_only: bool = False,
        before: UUID | None = None,
        limit: int = 50,
        topics: TopicFilter = NO_TOPIC_FILTER,
        period: Period = ANY_TIME,
        sort: Sort = Sort.DATE,
        group: InGroup | None = None,
    ) -> list[FeedItem]:
        return self._store.feed(
            context.workspace_id,
            context.user_id,
            view=view,
            source_id=source_id,
            unread_only=unread_only,
            before=before,
            limit=min(max(limit, 1), FEED_MAX),
            topics=topics,
            period=period,
            sort=sort,
            group=group,
        )

    def groups(
        self,
        context: WorkspaceContext,
        *,
        by: GroupBy,
        view: View = View.TO_SORT,
        source_id: UUID | None = None,
        unread_only: bool = False,
        topics: TopicFilter = NO_TOPIC_FILTER,
        period: Period = ANY_TIME,
    ) -> list[Group]:
        return self._store.groups(
            context.workspace_id,
            context.user_id,
            by=by,
            view=view,
            source_id=source_id,
            unread_only=unread_only,
            topics=topics,
            period=period,
        )

    def triage(self, context: WorkspaceContext, item_id: UUID) -> Triage | None:
        return self._store.triage(context.workspace_id, context.user_id, item_id)

    def change(self, context: WorkspaceContext, item_id: UUID, change: Change) -> Triage | None:
        return self._store.change(context.workspace_id, context.user_id, item_id, change)

    def change_many(self, context: WorkspaceContext, item_ids: list[UUID], change: Change) -> int:
        """The same change for several items at once (bulk actions of the feed)."""
        unique = list(dict.fromkeys(item_ids))[:BULK_MAX]
        return self._store.change_many(context.workspace_id, context.user_id, unique, change)

    def progress(self, context: WorkspaceContext) -> Progress:
        return self._store.progress(context.workspace_id, context.user_id)
