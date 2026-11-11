# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sends to WordPress on a real PostgreSQL, against a WordPress kept in memory (U07, ADR-0026):
a draft, its update, the publication, the update of the published post, no duplicate after a
failure, and a site never seen by another workspace."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import pytest

from integration_support import TestDatabase, requires_database
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.publishing.adapters.jobs import content
from otlet.publishing.adapters.postgres import PostgresPublishing, PostgresValidated
from otlet.publishing.application.publishing import (
    Publishing,
    SiteError,
    run_check,
    run_send,
)
from otlet.publishing.domain.model import Action, Post, PublishingError, Site, State, Term
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces
from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.adapters.articles_postgres import PostgresArticleStore

pytestmark = requires_database

DOCUMENT = {
    "type": "doc",
    "attrs": {
        "version_schema": 1,
        "langue": "fr",
        "sources": [
            {
                "id": "S1",
                "titre": "Le Grand Prix",
                "url": "https://journal.example.org/gp",
                "editeur": "Journal",
                "date": "2026-11-08",
            }
        ],
    },
    "content": [
        {
            "type": "paragraph",
            "attrs": {"id": "b1", "origine": "ia"},
            "content": [{"type": "text", "text": "Márquez gagne le sprint."}],
        },
        {"type": "image", "attrs": {"id": "b2", "media": "00000000-0000-0000-0000-000000000000"}},
    ],
}


@dataclass
class FakeWordPress:
    posts: dict[int, dict[str, Any]] = field(default_factory=dict)
    tags_known: dict[str, int] = field(default_factory=lambda: {"MotoGP": 7})
    fail_after_create: bool = False
    calls: list[str] = field(default_factory=list)
    created: int = 0

    def me(self) -> str:
        return "author"

    def categories(self) -> list[Term]:
        return [Term(3, "Sport")]

    def tags(self) -> list[Term]:
        return [Term(i, n) for n, i in self.tags_known.items()]

    def tag_ids(self, names: Sequence[str]) -> list[int]:
        for name in names:
            self.tags_known.setdefault(name, 100 + len(self.tags_known))
        return [self.tags_known[n] for n in names]

    def get(self, post_id: int) -> dict[str, Any] | None:
        post = self.posts.get(post_id)
        return None if post is None else {**post, "id": post_id}

    def find(self, marker: str) -> list[dict[str, Any]]:
        return [
            {**p, "id": i}
            for i, p in self.posts.items()
            if p["slug"] == f"otlet-{marker}" or f"otlet:{marker}" in p["raw_content"]
        ]

    def _save(self, post_id: int, post: Post) -> dict[str, Any]:
        current = self.posts.get(post_id, {})
        self.posts[post_id] = {
            "status": post.status,
            "raw_content": post.content,
            # An empty slug: WordPress makes one from the title.
            "slug": post.slug or (current.get("slug") if post.slug is None else None) or "le-gp",
            "link": f"http://site.test/?p={post_id}",
            "title": post.title,
            "categories": list(post.categories),
            "tags": list(post.tags),
        }
        return {**self.posts[post_id], "id": post_id}

    def create(self, post: Post) -> dict[str, Any]:
        self.calls.append("create")
        self.created += 1
        saved = self._save(self.created, post)
        if self.fail_after_create:
            self.fail_after_create = False
            raise SiteError("unreachable", "the answer was lost")
        return saved

    def update(self, post_id: int, post: Post) -> dict[str, Any]:
        self.calls.append(f"update {post_id}")
        return self._save(post_id, post)


class Sealer:
    def seal(self, plaintext: bytes, context: bytes) -> bytes:
        return b"sealed:" + plaintext


def context_of(engine: Any, email: str) -> WorkspaceContext:
    auth = Authentication(PostgresIdentityStore(engine), Argon2Hasher())
    workspaces = Workspaces(PostgresWorkspaceStore(engine))
    user = auth.create_user(email, email, "une phrase de passe assez longue")
    context = workspaces.enter(user, workspaces.create(user, email).id)
    assert context is not None
    return context


def test_a_draft_then_its_publication_update_the_same_post(migrated: TestDatabase) -> None:
    engine = db.create_engine(migrated.app_url)
    alice, bob = context_of(engine, "alice@example.org"), context_of(engine, "bob@example.org")
    jobs: list[tuple[str, dict[str, str]]] = []

    def enqueue(connection: Any, name: str, **kwargs: str) -> int:
        jobs.append((name, kwargs))
        return len(jobs)

    store = PostgresPublishing(engine, enqueue)
    articles_store = PostgresArticleStore(engine, lambda connection, name, **kwargs: 0)
    articles = PostgresValidated(engine, lambda *args: "open")
    publishing = Publishing(store, Sealer(), articles, lambda url: "10.0.0." in url)
    wordpress = FakeWordPress()

    def remote(site: Site) -> FakeWordPress:
        return wordpress

    # A site: its password sealed, « Tester » started at once; refused on an internal address.
    with pytest.raises(PublishingError) as caught:
        publishing.add_site(
            alice, name="Mon site", url="http://10.0.0.5", username="a", password="x" * 24
        )
    assert caught.value.code == "address_not_allowed"
    site = publishing.add_site(
        alice, name="Mon site", url="http://site.test/", username="otlet", password="abcd " * 6
    )
    assert (site.url, site.password_hint, site.check_pending) == ("http://site.test", "abcd", True)
    assert jobs[-1][0] == "publishing.check_site"
    run_check(store, remote, alice.workspace_id, site.id)
    checked = store.site(alice.workspace_id, site.id)
    assert checked is not None and (checked.check_result, checked.check_role) == ("ok", "author")
    assert checked.categories == (Term(3, "Sport"),) and not checked.check_pending
    assert publishing.sites(bob) == [] and store.password(bob.workspace_id, site.id) is None

    # Only a validated article goes out.
    article = articles_store.create_article(alice.workspace_id, alice.user_id, "Le GP", DOCUMENT)
    with pytest.raises(PublishingError) as caught:
        publishing.send(alice, article, site.id, Action.DRAFT, [], [])
    assert caught.value.code == "not_validated"
    assert articles_store.send(alice.workspace_id, article, 1)

    def send(action: Action, categories: list[int] = [], tags: list[str] = []) -> Any:  # noqa: B006
        publication = publishing.send(alice, article, site.id, action, categories, tags)
        assert publication.state is State.PENDING and jobs[-1][0] == "publishing.send"
        run_send(
            store,
            articles,
            content,
            remote,
            alice.workspace_id,
            publication.id,
            alice.user_id,
            sleep=lambda s: None,
        )
        found = store.publication(alice.workspace_id, publication.id)
        assert found is not None
        return found

    # 1. A draft: created, with the mark of ADR-0026 in its slug and content, no image.
    first = send(Action.DRAFT, [3], ["MotoGP", "Qatar"])
    assert (first.state, first.remote_id, first.remote_status, first.version) == (
        State.DONE,
        1,
        "draft",
        1,
    )
    post = wordpress.posts[1]
    assert post["slug"] == f"otlet-{first.marker}"
    assert post["raw_content"].startswith(f"<!-- otlet:{first.marker} -->")
    assert "Márquez gagne le sprint." in post["raw_content"] and "<img" not in post["raw_content"]
    assert "Sources" in post["raw_content"] and post["categories"] == [3]
    assert post["tags"] == [7, wordpress.tags_known["Qatar"]]
    # 2. Again as a draft: the same post is updated.
    second = send(Action.DRAFT)
    assert second.remote_id == 1 and wordpress.calls == ["create", "update 1"]
    # 3. « Publier »: the same post goes on line.
    third = send(Action.PUBLISH)
    assert (third.remote_id, third.remote_status) == (1, "publish")
    # Published, the post drops the otlet-<key> slug for the one WordPress makes from the title.
    assert wordpress.posts[1]["slug"] == "le-gp"
    # 4. Published, a draft is refused: Otlet never takes it off line by itself.
    with pytest.raises(PublishingError) as caught:
        publishing.send(alice, article, site.id, Action.DRAFT, [], [])
    assert caught.value.code == "already_published"
    # 5. Published again: the post on line is updated.
    assert send(Action.PUBLISH).remote_id == 1 and len(wordpress.posts) == 1
    events = publishing.events(alice, first.id)
    assert [e.result for e in events] == ["done"] * 4 and events[0].action == "publish"
    assert publishing.publications(bob, article) == []

    # The post deleted in WordPress: said, and the next send makes a new one.
    del wordpress.posts[1]
    gone = send(Action.PUBLISH)
    assert (gone.state, gone.error) == (State.FAILED, "remote_deleted")
    again = send(Action.DRAFT)
    assert again.state is State.DONE and again.remote_id == 2


def test_no_duplicate_when_the_answer_of_the_site_is_lost(migrated: TestDatabase) -> None:
    """ADR-0026 §2: the site created the post but its answer was lost; the mark finds it."""
    engine = db.create_engine(migrated.app_url)
    alice = context_of(engine, "carla@example.org")
    store = PostgresPublishing(engine, lambda connection, name, **kwargs: 0)
    articles_store = PostgresArticleStore(engine, lambda connection, name, **kwargs: 0)
    articles = PostgresValidated(engine, lambda *args: "open")
    publishing = Publishing(store, Sealer(), articles, lambda url: False)
    wordpress = FakeWordPress(fail_after_create=True)
    site = publishing.add_site(
        alice, name="Site", url="https://site.test", username="otlet", password="y" * 24
    )
    article = articles_store.create_article(alice.workspace_id, alice.user_id, "GP", DOCUMENT)
    assert articles_store.send(alice.workspace_id, article, 1)
    publication = publishing.send(alice, article, site.id, Action.PUBLISH, [], [])
    run_send(
        store,
        articles,
        content,
        lambda s: wordpress,
        alice.workspace_id,
        publication.id,
        alice.user_id,
        sleep=lambda s: None,
    )
    found = store.publication(alice.workspace_id, publication.id)
    assert found is not None and (found.state, found.remote_id) == (State.DONE, 1)
    assert len(wordpress.posts) == 1 and wordpress.calls == ["create"]
    # Two sends at once: the second is refused while the first is under way.
    publishing.send(alice, article, site.id, Action.PUBLISH, [], [])
    with pytest.raises(PublishingError) as caught:
        publishing.send(alice, article, site.id, Action.PUBLISH, [], [])
    assert caught.value.code == "send_running"


def test_a_site_that_refuses_says_why(migrated: TestDatabase) -> None:
    engine = db.create_engine(migrated.app_url)
    alice = context_of(engine, "dan@example.org")
    store = PostgresPublishing(engine, lambda connection, name, **kwargs: 0)
    publishing = Publishing(
        store, Sealer(), PostgresValidated(engine, lambda *a: "open"), lambda url: False
    )
    site = publishing.add_site(
        alice, name="Site", url="https://site.test", username="otlet", password="z" * 24
    )

    class Refusing(FakeWordPress):
        def me(self) -> str:
            raise SiteError("not_logged_in", "rest_not_logged_in")

    run_check(store, lambda s: Refusing(), alice.workspace_id, site.id)
    checked = store.site(alice.workspace_id, site.id)
    assert checked is not None and checked.check_result == "not_logged_in"
    assert publishing.delete_site(alice, site.id) and publishing.sites(alice) == []


def ids(found: Sequence[Any]) -> list[UUID]:
    return [f.id for f in found]
