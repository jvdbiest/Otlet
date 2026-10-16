# SPDX-License-Identifier: AGPL-3.0-or-later
"""Collection runs on a real PostgreSQL, against a simulated web (U01): the legal status of
each source (M-08), the compliance journal (CJ-03), deduplication, health and manual entry."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.collection.adapters.parsing import FeedparserReader, ReadabilityReader
from otlet.collection.adapters.postgres import PostgresCollectionStore
from otlet.collection.application.collection import (
    COLLECT_SOURCE,
    EXTRACT_ITEM,
    ITEM_READY,
    Collection,
)
from otlet.collection.domain.model import CollectionError, LegalStatus, TextStatus
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.platform.http import FetchError, FetchResult
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces
from otlet.workspaces.domain.model import WorkspaceContext

pytestmark = requires_database

SITE = "https://journal.example.org"
FEED = SITE + "/feed.xml"
NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def rss(*slugs: str) -> bytes:
    items = "".join(
        f"<item><title>Article {slug}</title><link>{SITE}/{slug}</link>"
        f"<guid>{SITE}/{slug}</guid><description>Résumé {slug}.</description></item>"
        for slug in slugs
    )
    return (
        f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
        f"<title>Le Journal</title><link>{SITE}/</link>{items}</channel></rss>"
    ).encode()


def article(slug: str, head: str = "") -> bytes:
    sentence = f"Le texte de l'article {slug}, assez long pour être retenu par la lecture. "
    return (
        f"<html><head><title>Article {slug}</title>{head}</head><body><article>"
        f"<p>{sentence * 4}</p><p>{sentence * 3}</p></article></body></html>"
    ).encode()


@dataclass
class Web:
    """URL → (status, headers, body); a missing URL answers 404, an exception is raised."""

    pages: dict[str, tuple[int, dict[str, str], bytes] | FetchError] = field(default_factory=dict)
    requested: list[tuple[str, Mapping[str, str]]] = field(default_factory=list)

    def get(
        self, url: str, *, headers: Mapping[str, str] | None = None, max_bytes: int = 0
    ) -> FetchResult:
        self.requested.append((url, dict(headers or {})))
        page = self.pages.get(url, (404, {}, b""))
        if isinstance(page, FetchError):
            raise page
        status, page_headers, body = page
        return FetchResult(status, url, {k.lower(): v for k, v in page_headers.items()}, body)


HTML = {"Content-Type": "text/html; charset=utf-8"}
XML = {"Content-Type": "application/rss+xml"}


@dataclass
class Queue:
    jobs: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def __call__(self, connection: sa.Connection, name: str, **kwargs: Any) -> int:
        self.jobs.append((name, kwargs))
        return len(self.jobs)

    def names(self) -> list[str]:
        return [name for name, _ in self.jobs]


@dataclass
class World:
    engine: sa.Engine
    web: Web
    queue: Queue
    collection: Collection
    context: WorkspaceContext
    clock: list[datetime]

    def run_jobs(self) -> None:
        """Runs the enqueued collection and extraction jobs, including those they enqueue."""
        while self.queue.jobs:
            name, kwargs = self.queue.jobs.pop(0)
            workspace = uuid.UUID(kwargs["workspace_id"])
            if name == COLLECT_SOURCE:
                self.collection.collect(workspace, uuid.UUID(kwargs["source_id"]))
            elif name == EXTRACT_ITEM:
                self.collection.extract(workspace, uuid.UUID(kwargs["item_id"]))


def make_context(engine: sa.Engine, login: str) -> WorkspaceContext:
    user = Authentication(PostgresIdentityStore(engine), Argon2Hasher()).create_user(
        login, login, "une phrase de passe assez longue"
    )
    workspaces = Workspaces(PostgresWorkspaceStore(engine))
    context = workspaces.enter(user, workspaces.create(user, "Veille").id)
    assert context is not None
    return context


@pytest.fixture
def world(migrated: TestDatabase) -> World:
    engine = db.create_engine(migrated.app_url)
    web, queue, clock = Web(), Queue(), [NOW]
    store = PostgresCollectionStore(engine, queue)
    collection = Collection(
        store, web, FeedparserReader(), ReadabilityReader(), clock=lambda: clock[0]
    )
    return World(engine, web, queue, collection, make_context(engine, "alice@example.org"), clock)


def open_site(web: Web, *slugs: str) -> None:
    web.pages[SITE + "/robots.txt"] = (200, {}, b"User-agent: *\nDisallow: /admin/\n")
    web.pages[FEED] = (200, XML, rss(*slugs))
    for slug in slugs:
        web.pages[f"{SITE}/{slug}"] = (200, HTML, article(slug))


def test_a_source_is_found_from_the_page_of_its_site(world: World) -> None:
    open_site(world.web, "a")
    world.web.pages[SITE + "/"] = (
        200,
        HTML,
        b'<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml">'
        b"</head><body></body></html>",
    )
    source = world.collection.add_source(world.context, "journal.example.org/")
    assert (source.name, source.feed_url, source.legal_status) == (
        "Le Journal",
        FEED,
        LegalStatus.UNKNOWN,
    )
    assert world.queue.names() == [COLLECT_SOURCE]
    with pytest.raises(CollectionError) as caught:
        world.collection.add_source(world.context, FEED)
    assert caught.value.code == "already_followed"


def test_a_page_without_feed_is_refused(world: World) -> None:
    world.web.pages[SITE + "/"] = (200, HTML, b"<html><body>Rien</body></html>")
    with pytest.raises(CollectionError) as caught:
        world.collection.add_source(world.context, SITE + "/")
    assert caught.value.code == "feed_not_found"


def test_an_open_source_brings_full_texts(world: World) -> None:
    open_site(world.web, "a", "b")
    source = world.collection.add_source(world.context, FEED)
    world.run_jobs()
    collected = world.collection.get_source(world.context, source.id)
    assert collected is not None
    assert (collected.legal_status, collected.item_count) == (LegalStatus.FULL_TEXT, 2)
    assert collected.last_success_at == NOW
    items = world.collection.list_items(world.context)
    assert {item.text_status for item in items} == {TextStatus.FULL_TEXT}
    full = world.collection.get_item(world.context, items[0].id)
    assert full is not None and full.text is not None and "assez long" in full.text
    checks = world.collection.checks(world.context, source.id)
    assert [(c.allowed, c.reason) for c in checks] == [(True, "tdm_not_reserved")]


def test_a_reserved_site_gives_summaries_only(world: World) -> None:
    open_site(world.web, "a")
    world.web.pages[SITE + "/.well-known/tdmrep.json"] = (
        200,
        {},
        b'[{"location": "/", "tdm-reservation": 1, "tdm-policy": "https://journal.example.org/p"}]',
    )
    source = world.collection.add_source(world.context, FEED)
    world.run_jobs()
    collected = world.collection.get_source(world.context, source.id)
    assert collected is not None
    assert (collected.legal_status, collected.legal_reason) == (
        LegalStatus.SUMMARY_ONLY,
        "tdm_reserved_file",
    )
    (item,) = world.collection.list_items(world.context)
    assert (item.text_status, item.text_reason, item.summary) == (
        TextStatus.SUMMARY_ONLY,
        "tdm_reserved_file",
        "Résumé a.",
    )
    # The page itself was never requested.
    assert f"{SITE}/a" not in [url for url, _ in world.web.requested]
    (check,) = world.collection.checks(world.context, source.id)
    assert (check.allowed, check.reason, check.detail) == (
        False,
        "tdm_reserved_file",
        "https://journal.example.org/p",
    )


def test_a_page_reserved_by_its_meta_tag_keeps_only_its_summary(world: World) -> None:
    open_site(world.web, "a")
    world.web.pages[f"{SITE}/a"] = (
        200,
        HTML,
        article("a", '<meta name="tdm-reservation" content="1">'),
    )
    world.collection.add_source(world.context, FEED)
    world.run_jobs()
    (item,) = world.collection.list_items(world.context)
    full = world.collection.get_item(world.context, item.id)
    assert full is not None
    assert (full.text_status, full.text_reason, full.text) == (
        TextStatus.SUMMARY_ONLY,
        "tdm_reserved_meta",
        None,
    )


@pytest.mark.parametrize(
    ("robots", "reason"),
    [
        ((200, {}, b"User-agent: Otlet\nDisallow: /\n"), "robots_disallowed"),
        ((503, {}, b""), "robots_unreachable"),
        (FetchError("timeout"), "robots_unreachable"),
    ],
)
def test_a_feed_closed_by_robots_is_refused(
    world: World, robots: tuple[int, dict[str, str], bytes] | FetchError, reason: str
) -> None:
    open_site(world.web, "a")
    world.web.pages[SITE + "/robots.txt"] = robots
    source = world.collection.add_source(world.context, FEED)
    world.run_jobs()
    refused = world.collection.get_source(world.context, source.id)
    assert refused is not None
    assert (refused.legal_status, refused.legal_reason, refused.item_count) == (
        LegalStatus.REFUSED,
        reason,
        0,
    )
    # The feed was read once, by the user's addition; never by the collection.
    assert [url for url, _ in world.web.requested].count(FEED) == 1


def test_a_second_run_brings_only_new_items_and_uses_conditional_requests(
    world: World,
) -> None:
    open_site(world.web, "a")
    world.web.pages[FEED] = (200, {**XML, "ETag": '"v1"'}, rss("a"))
    source = world.collection.add_source(world.context, FEED)
    world.run_jobs()
    open_site(world.web, "a", "b")
    world.web.pages[FEED] = (200, {**XML, "ETag": '"v2"'}, rss("a", "b"))
    world.collection.collect(world.context.workspace_id, source.id)
    assert world.web.requested[-1] == (FEED, {"If-None-Match": '"v1"'})
    world.run_jobs()
    assert [i.title for i in world.collection.list_items(world.context)] == [
        "Article b",
        "Article a",
    ]
    world.web.pages[FEED] = (304, {}, b"")
    world.collection.collect(world.context.workspace_id, source.id)
    assert world.web.requested[-1] == (FEED, {"If-None-Match": '"v2"'})
    assert len(world.collection.list_items(world.context)) == 2


def test_failures_degrade_the_source_and_space_out_the_retries(world: World) -> None:
    open_site(world.web, "a")
    source = world.collection.add_source(world.context, FEED)
    world.queue.jobs.clear()
    world.web.pages[FEED] = FetchError("network_error")
    for _ in range(3):
        world.collection.collect(world.context.workspace_id, source.id)
    failing = world.collection.get_source(world.context, source.id)
    assert failing is not None
    assert (failing.health.value, failing.consecutive_failures, failing.last_error) == (
        "degraded",
        3,
        "fetch_network_error",
    )
    assert failing.next_fetch_at == NOW + timedelta(minutes=60 * 8)
    world.web.pages[FEED] = (200, XML, rss("a"))
    world.collection.collect(world.context.workspace_id, source.id)
    healed = world.collection.get_source(world.context, source.id)
    assert healed is not None and (healed.health.value, healed.last_error) == ("ok", None)


def test_due_sources_of_every_workspace_are_claimed_once(world: World) -> None:
    open_site(world.web, "a")
    other = make_context(world.engine, "bob@example.org")
    first = world.collection.add_source(world.context, FEED)
    second = world.collection.add_source(other, FEED)
    world.queue.jobs.clear()
    assert PostgresCollectionStore(world.engine, world.queue).claim_due_sources(100) == 2
    claimed = {(job["workspace_id"], job["source_id"]) for _, job in world.queue.jobs}
    assert claimed == {
        (str(world.context.workspace_id), str(first.id)),
        (str(other.workspace_id), str(second.id)),
    }
    assert PostgresCollectionStore(world.engine, world.queue).claim_due_sources(100) == 0
    # Outside that function, the application role sees no source without a context.
    with db.scoped_transaction(world.engine) as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM sources")).scalar_one() == 0


def test_a_pasted_text_keeps_its_declaration(world: World) -> None:
    with pytest.raises(CollectionError) as caught:
        world.collection.add_manual_text(
            world.context, title="Note", text="Texte", declared_origin="", usage_right="ok"
        )
    assert caught.value.code == "invalid_declaration"
    item = world.collection.add_manual_text(
        world.context,
        title="Note de réunion",
        text="Ce que j'ai écrit moi-même.",
        declared_origin="Mes notes personnelles",
        usage_right="Je suis l'auteur",
    )
    assert (item.origin.value, item.text_status, item.declared_origin, item.usage_right) == (
        "manual_text",
        TextStatus.MANUAL,
        "Mes notes personnelles",
        "Je suis l'auteur",
    )
    assert world.queue.names() == [ITEM_READY]


def test_a_pointed_page_is_read_under_the_same_rules(world: World) -> None:
    open_site(world.web, "a")
    item = world.collection.add_manual_url(world.context, f"{SITE}/a")
    assert (item.text_status, item.title) == (TextStatus.PENDING, f"{SITE}/a")
    world.run_jobs()
    read = world.collection.get_item(world.context, item.id)
    assert read is not None
    assert (read.text_status, read.title) == (TextStatus.FULL_TEXT, "Article a")


def test_another_workspace_sees_nothing(world: World) -> None:
    open_site(world.web, "a")
    source = world.collection.add_source(world.context, FEED)
    world.run_jobs()
    other = make_context(world.engine, "bob@example.org")
    assert world.collection.list_sources(other) == []
    assert world.collection.list_items(other) == []
    assert world.collection.get_source(other, source.id) is None
    assert not world.collection.delete_source(other, source.id)


def test_items_of_one_run_are_paged_without_loss(world: World) -> None:
    open_site(world.web, "a", "b", "c")
    world.collection.add_source(world.context, FEED)
    world.run_jobs()
    first = world.collection.list_items(world.context, limit=2)
    rest = world.collection.list_items(world.context, before=first[-1].id, limit=2)
    # The three items share their collected_at: the cursor is (collected_at, id).
    assert len({item.collected_at for item in first + rest}) == 1
    assert sorted(item.title for item in first + rest) == ["Article a", "Article b", "Article c"]
