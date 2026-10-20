# SPDX-License-Identifier: AGPL-3.0-or-later
"""What the collection needs from the outside world: storage, HTTP, feed and page parsing."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from otlet.collection.domain.compliance import Robots, TdmRule
from otlet.collection.domain.model import (
    Check,
    Decision,
    FeedEntry,
    Item,
    LegalStatus,
    Page,
    ParsedFeed,
    RightsDeclaration,
    Source,
    TextStatus,
)
from otlet.platform.http import FetchResult


class Fetcher(Protocol):
    def get(
        self, url: str, *, headers: Mapping[str, str] | None = None, max_bytes: int = ...
    ) -> FetchResult: ...


class FeedReader(Protocol):
    def read(self, body: bytes, url: str) -> ParsedFeed | None:
        """The feed, or None when `body` is not a feed."""
        ...

    def discover(self, html: str, url: str) -> list[str]:
        """The absolute URLs of the feeds an HTML page announces, in its order."""
        ...


class PageReader(Protocol):
    def extract(self, html: str, url: str) -> Page | None:
        """The main content of an article page, or None when none is found."""
        ...


@dataclass(frozen=True, slots=True)
class SitePolicy:
    robots: Robots
    tdm_rules: tuple[TdmRule, ...]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CollectionState:
    source: Source
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True, slots=True)
class Outcome:
    """The result of one collection run, written back to the source."""

    fetched_at: datetime
    next_fetch_at: datetime
    success: bool
    error: str | None = None
    legal_status: LegalStatus | None = None
    legal_reason: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    site_url: str | None = None


@dataclass(frozen=True, slots=True)
class NewItem:
    entry: FeedEntry
    text_status: TextStatus
    text_reason: str | None


class CollectionStore(Protocol):
    # Sources
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
        """Creates the source and enqueues its first collection in the same transaction."""
        ...

    def list_sources(self, workspace_id: UUID) -> list[Source]: ...
    def get_source(self, workspace_id: UUID, source_id: UUID) -> Source | None: ...

    def update_source(
        self,
        workspace_id: UUID,
        source_id: UUID,
        *,
        name: str | None,
        interval_minutes: int | None,
        active: bool | None,
        address: tuple[str, str, str | None] | None = None,
    ) -> Source | None:
        """`address`: a new (url, feed_url, site_url); the source is then checked again from
        scratch at once. CollectionError « already_followed » when another source has the feed."""
        ...

    def delete_source(self, workspace_id: UUID, source_id: UUID) -> bool: ...
    def request_collection(self, workspace_id: UUID, source_id: UUID) -> bool: ...

    # Collection runs
    def claim_due_sources(self, limit: int) -> int:
        """Enqueues the collection of the sources that are due, in every workspace, and returns
        how many; a claimed source is not due again before its next interval."""
        ...

    def collection_state(self, workspace_id: UUID, source_id: UUID) -> CollectionState | None: ...

    def finish_collection(
        self, workspace_id: UUID, source_id: UUID, outcome: Outcome, items: list[NewItem]
    ) -> int:
        """Writes the outcome and the items not seen before, enqueues the reading of the new
        pending items, and returns how many items are new."""
        ...

    def record_check(
        self, workspace_id: UUID, source_id: UUID | None, url: str, decision: Decision
    ) -> None: ...

    def list_checks(self, workspace_id: UUID, source_id: UUID, limit: int) -> list[Check]: ...

    # Items
    def list_items(
        self, workspace_id: UUID, *, source_id: UUID | None, before: UUID | None, limit: int
    ) -> list[Item]: ...

    def get_item(self, workspace_id: UUID, item_id: UUID) -> Item | None: ...
    def pending_item_url(self, workspace_id: UUID, item_id: UUID) -> str | None: ...

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
        """Writes the text of a read page and announces the item as ready (ITEM_READY)."""
        ...

    def remove_item(self, workspace_id: UUID, item_id: UUID) -> bool:
        """Deletes an item of the workspace with its text, matches and triage; an item of a feed
        leaves a trace so that its next collection skips it. False when there is no such item."""
        ...

    def declare_rights(self, workspace_id: UUID, declaration: RightsDeclaration) -> bool:
        """Keeps the declaration, sets the reserved item back to pending and enqueues its
        reading under the declaration, in one transaction; False when the item is not reserved."""
        ...

    def rights_declaration(self, workspace_id: UUID, item_id: UUID) -> RightsDeclaration | None:
        """The declaration in force on an item, if any."""
        ...

    def withdraw_rights(self, workspace_id: UUID, item_id: UUID, at: datetime) -> bool:
        """Withdraws the declaration in force: its text is erased, the reservation comes back."""
        ...

    def retry_text(self, workspace_id: UUID, item_id: UUID) -> bool:
        """Sets an item whose text was missed back to pending and enqueues its reading, in one
        transaction; False when it is unknown or its text cannot be retried."""
        ...

    def add_manual_url(self, workspace_id: UUID, url: str, at: datetime) -> Item:
        """Creates a pending item and enqueues the reading of its page."""
        ...

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
    ) -> Item: ...

    # Cache of robots.txt and tdmrep.json, per origin
    def site_policy(self, workspace_id: UUID, origin: str) -> SitePolicy | None: ...
    def save_site_policy(self, workspace_id: UUID, origin: str, policy: SitePolicy) -> None: ...
