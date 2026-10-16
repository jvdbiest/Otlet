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
    NO_TOPIC_FILTER,
    Decision,
    Progress,
    TopicFilter,
    Triage,
    View,
)
from otlet.workspaces.domain.model import WorkspaceContext

FEED_MAX = 200


@dataclass(frozen=True, slots=True)
class FeedItem:
    item: Item
    triage: Triage


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
    ) -> list[FeedItem]: ...

    def triage(self, workspace_id: UUID, user_id: UUID, item_id: UUID) -> Triage | None:
        """The triage of an item of the workspace (the default for one never sorted), or None
        when the item does not exist."""
        ...

    def change(
        self, workspace_id: UUID, user_id: UUID, item_id: UUID, change: Change
    ) -> Triage | None: ...

    def progress(self, workspace_id: UUID, user_id: UUID) -> Progress: ...


class Feed:
    def __init__(self, store: TriageStore) -> None:
        self._store = store

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
        )

    def triage(self, context: WorkspaceContext, item_id: UUID) -> Triage | None:
        return self._store.triage(context.workspace_id, context.user_id, item_id)

    def change(self, context: WorkspaceContext, item_id: UUID, change: Change) -> Triage | None:
        return self._store.change(context.workspace_id, context.user_id, item_id, change)

    def progress(self, context: WorkspaceContext) -> Progress:
        return self._store.progress(context.workspace_id, context.user_id)
