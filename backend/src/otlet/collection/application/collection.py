# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sources, collection runs and manual entry (U01, ARCHITECTURE §13.1, RISKS M-08).

The network is never used inside a database transaction: a run reads the state of its source,
fetches, then writes the outcome in one transaction.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

from otlet.collection.application.ports import (
    CollectionStore,
    FeedReader,
    Fetcher,
    NewItem,
    Outcome,
    PageReader,
    SitePolicy,
)
from otlet.collection.domain import compliance, model
from otlet.collection.domain.compliance import Robots, RobotsKind
from otlet.collection.domain.model import (
    CollectionError,
    Decision,
    Item,
    LegalStatus,
    Source,
    TextStatus,
)
from otlet.platform.http import FetchError
from otlet.workspaces.domain.model import WorkspaceContext

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]

SITE_POLICY_LIFETIME = timedelta(hours=24)
ROBOTS_MAX_BYTES = 512 * 1024
TDMREP_MAX_BYTES = 256 * 1024
FEED_MAX_BYTES = 10 * 1024 * 1024
PAGE_MAX_BYTES = 5 * 1024 * 1024
DISCOVERY_CANDIDATES = 3
CLAIM_BATCH = 100
HTML_TYPES = ("text/html", "application/xhtml+xml")
# Jobs of the module (otlet.collection.adapters.jobs), enqueued by the store; the scheduler
# enqueues the collections that are due (otlet.entrypoints.scheduler).
COLLECT_SOURCE = "collection.collect_source"
EXTRACT_ITEM = "collection.extract_item"
# Event for the watch module: an item has its final text (otlet.watch.adapters.jobs).
ITEM_READY = "watch.item_ready"


def utc_now() -> datetime:
    return datetime.now(UTC)


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme.lower()}://{(parts.netloc or '').lower()}"


@dataclass(frozen=True, slots=True)
class PageReading:
    status: TextStatus
    reason: str
    text: str | None = None
    title: str | None = None
    language: str | None = None


class SitePolicies:
    """robots.txt and tdmrep.json of each origin, cached for a day in the workspace."""

    def __init__(self, store: CollectionStore, fetcher: Fetcher, clock: Clock) -> None:
        self._store = store
        self._fetcher = fetcher
        self._clock = clock

    def for_url(self, workspace_id: UUID, url: str) -> SitePolicy:
        origin = origin_of(url)
        cached = self._store.site_policy(workspace_id, origin)
        now = self._clock()
        if cached is not None and cached.expires_at > now:
            return cached
        policy = SitePolicy(
            robots=self._robots(origin),
            tdm_rules=self._tdm_rules(origin),
            expires_at=now + SITE_POLICY_LIFETIME,
        )
        self._store.save_site_policy(workspace_id, origin, policy)
        return policy

    def _robots(self, origin: str) -> Robots:
        try:
            result = self._fetcher.get(origin + "/robots.txt", max_bytes=ROBOTS_MAX_BYTES)
        except FetchError as error:
            logger.info("robots.txt of %s unreachable: %s", origin, error)
            return Robots(RobotsKind.UNREACHABLE)
        kind = compliance.robots_kind(result.status)
        return Robots(kind, result.text() if kind is RobotsKind.FOUND else "")

    def _tdm_rules(self, origin: str) -> tuple[compliance.TdmRule, ...]:
        try:
            result = self._fetcher.get(
                origin + "/.well-known/tdmrep.json", max_bytes=TDMREP_MAX_BYTES
            )
        except FetchError:
            return ()
        return compliance.parse_tdmrep(result.text()) if result.status == 200 else ()


def fetch_error(error: FetchError) -> CollectionError:
    return CollectionError(f"fetch_{error.reason}", f"the address could not be read ({error})")


class Collection:
    def __init__(
        self,
        store: CollectionStore,
        fetcher: Fetcher,
        feeds: FeedReader,
        pages: PageReader,
        clock: Clock = utc_now,
    ) -> None:
        self._store = store
        self._fetcher = fetcher
        self._feeds = feeds
        self._pages = pages
        self._clock = clock
        self._policies = SitePolicies(store, fetcher, clock)

    # Sources -----------------------------------------------------------------------------

    def add_source(
        self,
        context: WorkspaceContext,
        url: str,
        name: str | None = None,
        interval_minutes: int = model.INTERVAL_DEFAULT_MINUTES,
    ) -> Source:
        """Follows the feed at `url`, or the first feed the page at `url` announces
        (F-SRC-01). Its first collection is enqueued at once."""
        entered = model.check_url(url)
        interval = model.check_interval(interval_minutes)
        feed_url, feed = self._find_feed(entered)
        host = urlsplit(feed_url).hostname or feed_url
        return self._store.add_source(
            context.workspace_id,
            name=model.check_name(name or feed.title or host),
            url=entered,
            feed_url=feed_url,
            site_url=feed.site_url,
            interval_minutes=interval,
        )

    def _find_feed(self, url: str) -> tuple[str, model.ParsedFeed]:
        try:
            result = self._fetcher.get(url, max_bytes=FEED_MAX_BYTES)
        except FetchError as error:
            raise fetch_error(error) from error
        if result.status >= 400:
            raise CollectionError("fetch_http_error", f"the address answered {result.status}")
        feed = self._feeds.read(result.body, result.url)
        if feed is not None:
            return result.url, feed
        if result.content_type in HTML_TYPES:
            for candidate in self._feeds.discover(result.text(), result.url)[:DISCOVERY_CANDIDATES]:
                try:
                    found = self._fetcher.get(candidate, max_bytes=FEED_MAX_BYTES)
                except FetchError:
                    continue
                feed = self._feeds.read(found.body, found.url) if found.status < 400 else None
                if feed is not None:
                    return found.url, feed
        raise CollectionError("feed_not_found", "no RSS, Atom or JSON feed found at this address")

    def list_sources(self, context: WorkspaceContext) -> list[Source]:
        return self._store.list_sources(context.workspace_id)

    def get_source(self, context: WorkspaceContext, source_id: UUID) -> Source | None:
        return self._store.get_source(context.workspace_id, source_id)

    def update_source(
        self,
        context: WorkspaceContext,
        source_id: UUID,
        *,
        name: str | None = None,
        interval_minutes: int | None = None,
        active: bool | None = None,
    ) -> Source | None:
        return self._store.update_source(
            context.workspace_id,
            source_id,
            name=None if name is None else model.check_name(name),
            interval_minutes=None
            if interval_minutes is None
            else model.check_interval(interval_minutes),
            active=active,
        )

    def delete_source(self, context: WorkspaceContext, source_id: UUID) -> bool:
        return self._store.delete_source(context.workspace_id, source_id)

    def collect_now(self, context: WorkspaceContext, source_id: UUID) -> bool:
        return self._store.request_collection(context.workspace_id, source_id)

    def checks(self, context: WorkspaceContext, source_id: UUID) -> list[model.Check]:
        return self._store.list_checks(context.workspace_id, source_id, limit=50)

    # Items --------------------------------------------------------------------------------

    def list_items(
        self,
        context: WorkspaceContext,
        *,
        source_id: UUID | None = None,
        before: UUID | None = None,
        limit: int = 50,
    ) -> list[Item]:
        return self._store.list_items(
            context.workspace_id, source_id=source_id, before=before, limit=min(limit, 200)
        )

    def get_item(self, context: WorkspaceContext, item_id: UUID) -> Item | None:
        return self._store.get_item(context.workspace_id, item_id)

    def add_manual_url(self, context: WorkspaceContext, url: str) -> Item:
        """An article the user points to: its page is read under the same rules as a feed's."""
        return self._store.add_manual_url(context.workspace_id, model.check_url(url), self._clock())

    def add_manual_text(
        self,
        context: WorkspaceContext,
        *,
        title: str,
        text: str,
        declared_origin: str,
        usage_right: str,
        url: str | None = None,
    ) -> Item:
        """A text the user pastes (M-08): Otlet cannot check its rights, so the user declares
        where it comes from and what they may do with it, and the item stays marked."""
        clean_title, clean_text = model.check_manual_text(title, text)
        return self._store.add_manual_text(
            context.workspace_id,
            title=clean_title,
            text=clean_text,
            url=None if not url else model.check_url(url),
            declared_origin=model.check_declaration(declared_origin, "declared origin"),
            usage_right=model.check_declaration(usage_right, "right of use"),
            at=self._clock(),
        )

    # Background runs ------------------------------------------------------------------------

    def collect(self, workspace_id: UUID, source_id: UUID) -> None:
        """One collection run of a source (the job collection.collect_source)."""
        state = self._store.collection_state(workspace_id, source_id)
        if state is None or not state.source.active:
            return
        source = state.source
        now = self._clock()
        policy = self._policies.for_url(workspace_id, source.feed_url)
        allowed = policy.robots.decide(source.feed_url)
        if not allowed.allowed:
            self._note(workspace_id, source, source.feed_url, allowed, LegalStatus.REFUSED)
            self._store.finish_collection(
                workspace_id,
                source_id,
                self._outcome(source, now, success=True, legal=(LegalStatus.REFUSED, allowed)),
                [],
            )
            return

        headers = {}
        if state.etag:
            headers["If-None-Match"] = state.etag
        if state.last_modified:
            headers["If-Modified-Since"] = state.last_modified
        try:
            result = self._fetcher.get(source.feed_url, headers=headers, max_bytes=FEED_MAX_BYTES)
        except FetchError as error:
            self._fail(workspace_id, source, now, f"fetch_{error.reason}")
            return
        if result.not_modified:
            self._store.finish_collection(
                workspace_id,
                source_id,
                self._outcome(
                    source, now, success=True, etag=state.etag, modified=state.last_modified
                ),
                [],
            )
            return
        if result.status >= 400:
            self._fail(workspace_id, source, now, f"http_{result.status}")
            return
        feed = self._feeds.read(result.body, result.url)
        if feed is None:
            self._fail(workspace_id, source, now, "not_a_feed")
            return

        feed_mining = compliance.mining(source.feed_url, policy.tdm_rules, dict(result.headers))
        legal = self._source_decision(workspace_id, feed, feed_mining)
        self._note(workspace_id, source, source.feed_url, legal[1], legal[0])
        items = [self._new_item(entry, feed_mining) for entry in feed.entries]
        new = self._store.finish_collection(
            workspace_id,
            source_id,
            self._outcome(
                source,
                now,
                success=True,
                legal=legal,
                etag=result.headers.get("etag"),
                modified=result.headers.get("last-modified"),
                site_url=feed.site_url,
            ),
            items,
        )
        logger.info("source %s: %s entries, %s new", source_id, len(items), new)

    def _source_decision(
        self, workspace_id: UUID, feed: model.ParsedFeed, feed_mining: Decision
    ) -> tuple[LegalStatus, Decision]:
        """The legal status of a source: refused is handled before; summary only when the
        feed is reserved or when the pages of its first entry may not be read or mined."""
        if not feed_mining.allowed:
            return LegalStatus.SUMMARY_ONLY, feed_mining
        sample = next((entry.url for entry in feed.entries if entry.url), None)
        if sample is None:
            return LegalStatus.FULL_TEXT, feed_mining
        policy = self._policies.for_url(workspace_id, sample)
        page_robots = policy.robots.decide(sample)
        if not page_robots.allowed:
            return LegalStatus.SUMMARY_ONLY, page_robots
        page_file = compliance.file_reservation(sample, policy.tdm_rules)
        if page_file is not None and not page_file.allowed:
            return LegalStatus.SUMMARY_ONLY, page_file
        return LegalStatus.FULL_TEXT, page_file or feed_mining

    @staticmethod
    def _new_item(entry: model.FeedEntry, feed_mining: Decision) -> NewItem:
        if not feed_mining.allowed:
            return NewItem(entry, TextStatus.SUMMARY_ONLY, feed_mining.reason)
        if entry.url is None:
            # Nothing more to read: the feed is all there is.
            status = TextStatus.FULL_TEXT if entry.content else TextStatus.SUMMARY_ONLY
            return NewItem(entry, status, "feed_only")
        return NewItem(entry, TextStatus.PENDING, None)

    def _note(
        self,
        workspace_id: UUID,
        source: Source,
        url: str,
        decision: Decision,
        status: LegalStatus,
    ) -> None:
        """Writes the decision to the compliance journal when the status of the source changes:
        the journal tells when and why, without one line per run."""
        if (source.legal_status, source.legal_reason) != (status, decision.reason):
            self._store.record_check(workspace_id, source.id, url, decision)

    def _outcome(
        self,
        source: Source,
        now: datetime,
        *,
        success: bool,
        error: str | None = None,
        legal: tuple[LegalStatus, Decision] | None = None,
        etag: str | None = None,
        modified: str | None = None,
        site_url: str | None = None,
    ) -> Outcome:
        failures = 0 if success else source.consecutive_failures + 1
        return Outcome(
            fetched_at=now,
            next_fetch_at=now + model.next_fetch_delay(source.interval_minutes, failures),
            success=success,
            error=error,
            legal_status=None if legal is None else legal[0],
            legal_reason=None if legal is None else legal[1].reason,
            etag=etag,
            last_modified=modified,
            site_url=site_url,
        )

    def _fail(self, workspace_id: UUID, source: Source, now: datetime, error: str) -> None:
        logger.info("source %s failed: %s", source.id, error)
        self._store.finish_collection(
            workspace_id, source.id, self._outcome(source, now, success=False, error=error), []
        )

    def extract(self, workspace_id: UUID, item_id: UUID) -> None:
        """Reads the page of a pending item and keeps its text when the site allows it
        (the job collection.extract_item)."""
        url = self._store.pending_item_url(workspace_id, item_id)
        if url is None:
            return
        reading = self._read_page(workspace_id, url)
        self._store.set_item_text(
            workspace_id,
            item_id,
            status=reading.status,
            reason=reading.reason,
            text=reading.text,
            title=reading.title,
            language=reading.language,
            at=self._clock(),
        )

    def _read_page(self, workspace_id: UUID, url: str) -> PageReading:
        policy = self._policies.for_url(workspace_id, url)
        robots = policy.robots.decide(url)
        if not robots.allowed:
            return PageReading(TextStatus.SUMMARY_ONLY, robots.reason)
        reserved = compliance.file_reservation(url, policy.tdm_rules)
        if reserved is not None and not reserved.allowed:
            return PageReading(TextStatus.SUMMARY_ONLY, reserved.reason)
        try:
            result = self._fetcher.get(url, max_bytes=PAGE_MAX_BYTES)
        except FetchError as error:
            return PageReading(TextStatus.SUMMARY_ONLY, f"fetch_{error.reason}")
        if result.status >= 400:
            return PageReading(TextStatus.SUMMARY_ONLY, f"http_{result.status}")
        if result.content_type not in HTML_TYPES:
            return PageReading(TextStatus.SUMMARY_ONLY, "not_html")
        html = result.text()
        mining = compliance.mining(url, policy.tdm_rules, dict(result.headers), html)
        page = self._pages.extract(html, result.url)
        title = page.title if page else None
        language = page.language if page else None
        if not mining.allowed:
            return PageReading(TextStatus.SUMMARY_ONLY, mining.reason, None, title, language)
        if page is None or not page.text.strip():
            return PageReading(TextStatus.SUMMARY_ONLY, "no_text_found", None, title, language)
        return PageReading(TextStatus.FULL_TEXT, mining.reason, page.text, title, language)
