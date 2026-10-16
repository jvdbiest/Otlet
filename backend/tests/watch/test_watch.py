# SPDX-License-Identifier: AGPL-3.0-or-later
"""Topics, duplicates and search on a real PostgreSQL (U02)."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.collection.adapters.postgres import PostgresCollectionStore
from otlet.collection.application.ports import NewItem, Outcome
from otlet.collection.domain.model import FeedEntry, TextStatus
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.watch.adapters.postgres import PostgresWatchStore
from otlet.watch.application.watch import ITEM_READY, RESCORE_TOPIC, Watch
from otlet.watch.domain.model import WatchError
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces
from otlet.workspaces.domain.model import WorkspaceContext

pytestmark = requires_database

NOW = datetime.now(UTC)
LONG = (
    "Le Parlement européen a adopté hier un texte sur l'intelligence artificielle qui encadre "
    "les usages à risque, après des mois de négociations entre les États membres et la "
    "Commission, et prévoit des sanctions pour les entreprises qui ne le respectent pas."
)


@dataclass
class Queue:
    jobs: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def __call__(self, connection: sa.Connection, name: str, **kwargs: Any) -> int:
        self.jobs.append((name, kwargs))
        return len(self.jobs)


@dataclass
class World:
    engine: sa.Engine
    queue: Queue
    collection: PostgresCollectionStore
    watch: Watch
    context: WorkspaceContext

    def source(self, name: str) -> uuid.UUID:
        return self.collection.add_source(
            self.context.workspace_id,
            name=name,
            url=f"https://{name}.example.org/feed",
            feed_url=f"https://{name}.example.org/feed",
            site_url=None,
            interval_minutes=60,
        ).id

    def publish(
        self,
        source_id: uuid.UUID,
        guid: str,
        title: str,
        content: str | None = None,
        *,
        url: str | None = None,
        language: str = "fr",
        status: TextStatus = TextStatus.FULL_TEXT,
        published: datetime | None = None,
    ) -> None:
        entry = FeedEntry(
            guid=guid,
            url=url,
            title=title,
            author=None,
            published_at=published or NOW,
            summary=None,
            content=content,
            language=language,
        )
        outcome = Outcome(fetched_at=NOW, next_fetch_at=NOW + timedelta(hours=1), success=True)
        self.collection.finish_collection(
            self.context.workspace_id, source_id, outcome, [NewItem(entry, status, "test")]
        )

    def run_jobs(self) -> None:
        while self.queue.jobs:
            name, kwargs = self.queue.jobs.pop(0)
            workspace = uuid.UUID(kwargs["workspace_id"])
            if name == ITEM_READY:
                self.watch.item_ready(workspace, uuid.UUID(kwargs["item_id"]))
            elif name == RESCORE_TOPIC:
                self.watch.rescore_topic(workspace, uuid.UUID(kwargs["topic_id"]), NOW)


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
    queue = Queue()
    return World(
        engine,
        queue,
        PostgresCollectionStore(engine, queue),
        Watch(PostgresWatchStore(engine, queue)),
        make_context(engine, "alice@example.org"),
    )


def titles(world: World, topic_id: uuid.UUID) -> list[str]:
    return [
        entry.item.title
        for entry in world.watch.topic_items(world.context, topic_id, NOW, limit=50, offset=0)
    ]


def test_a_new_topic_ranks_the_recent_items_with_explanations(world: World) -> None:
    lemonde = world.source("lemonde")
    world.publish(lemonde, "1", "L'IA au Parlement européen", LONG)
    world.publish(lemonde, "2", "Météo : un week-end ensoleillé", "Du soleil partout.")
    world.publish(
        lemonde, "3", "Une loi sur l'IA", "Le texte parle d'IA.", published=NOW - timedelta(days=5)
    )
    world.run_jobs()
    topic = world.watch.create_topic(
        world.context, name="Régulation de l'IA", keywords=["IA", "intelligence artificielle"]
    )
    world.run_jobs()
    scored = world.watch.topic_items(world.context, topic.id, NOW, limit=50, offset=0)
    assert [entry.item.title for entry in scored] == [
        "L'IA au Parlement européen",
        "Une loi sur l'IA",
    ]
    first = scored[0]
    assert first.freshness == 2
    assert first.score == sum(c.points for c in first.contributions) + first.freshness
    assert {(c.term, c.where) for c in first.contributions} == {
        ("IA", "title"),
        ("intelligence artificielle", "text"),
    }
    assert world.watch.get_topic(world.context, topic.id).item_count == 2  # type: ignore[union-attr]


def test_a_new_item_joins_the_existing_topics(world: World) -> None:
    topic = world.watch.create_topic(world.context, name="Énergie", keywords=["énergie"])
    world.run_jobs()
    source = world.source("journal")
    world.publish(source, "1", "Prix de l'énergie en hausse")
    world.run_jobs()
    (first,) = world.watch.item_topics(
        world.context,
        world.watch.topic_items(world.context, topic.id, NOW, limit=5, offset=0)[0].item.id,
    )
    assert (first.name, first.score) == ("Énergie", 3)


def test_the_same_story_from_two_sources_shows_once(world: World) -> None:
    topic = world.watch.create_topic(world.context, name="Parlement", keywords=["Parlement"])
    a, b, c = world.source("a"), world.source("b"), world.source("c")
    world.publish(
        a, "1", "Le Parlement européen adopte la loi sur l'IA", LONG, url="https://x.org/1"
    )
    world.publish(b, "2", "Le Parlement européen adopte la loi sur l'IA !", "Court.")
    world.publish(c, "3", "Autre titre", LONG)
    world.run_jobs()
    scored = world.watch.topic_items(world.context, topic.id, NOW, limit=50, offset=0)
    assert [entry.item.title for entry in scored] == [
        "Le Parlement européen adopte la loi sur l'IA"
    ]
    assert scored[0].item.duplicates == 2
    others = world.watch.duplicates(world.context, scored[0].item.id)
    assert {d.title for d in others} == {
        "Le Parlement européen adopte la loi sur l'IA !",  # nearly the same title
        "Autre titre",  # the same text
    }


def test_search_stems_each_language_and_skips_reserved_texts(world: World) -> None:
    source = world.source("mixed")
    world.publish(source, "1", "Les élections municipales", "Résultats des scrutins.")
    world.publish(source, "2", "Election results", "Voters went to the polls.", language="en")
    world.publish(
        source, "3", "Article réservé", "secret électoral", status=TextStatus.SUMMARY_ONLY
    )
    world.run_jobs()
    found = [f.item.title for f in world.watch.search(world.context, "élection")]
    assert found == ["Les élections municipales"]
    assert [f.item.title for f in world.watch.search(world.context, "voter")] == [
        "Election results"
    ]
    assert world.watch.search(world.context, "secret") == []
    with pytest.raises(WatchError):
        world.watch.search(world.context, "   ")


def test_topic_names_are_unique_and_other_workspaces_see_nothing(world: World) -> None:
    topic = world.watch.create_topic(world.context, name="IA", keywords=["IA"])
    with pytest.raises(WatchError) as caught:
        world.watch.create_topic(world.context, name="IA", keywords=["autre"])
    assert caught.value.code == "name_taken"
    other = make_context(world.engine, "bob@example.org")
    assert world.watch.list_topics(other) == []
    assert world.watch.get_topic(other, topic.id) is None
    assert not world.watch.delete_topic(other, topic.id)
    with pytest.raises(WatchError) as unknown:
        world.watch.create_topic(
            world.context, name="Ciblé", keywords=["x"], source_ids=[uuid.uuid4()]
        )
    assert unknown.value.code == "unknown_source"


def test_items_whose_event_was_lost_are_caught_up(world: World) -> None:
    topic = world.watch.create_topic(world.context, name="Énergie", keywords=["énergie"])
    world.run_jobs()
    other = make_context(world.engine, "bob@example.org")
    source = world.source("journal")
    world.publish(source, "1", "Prix de l'énergie")
    world.queue.jobs.clear()  # the ITEM_READY event is lost
    store = PostgresWatchStore(world.engine, world.queue)
    assert store.enqueue_unwatched(100, timedelta(0)) == 1
    assert [name for name, _ in world.queue.jobs] == [ITEM_READY]
    world.run_jobs()
    assert titles(world, topic.id) == ["Prix de l'énergie"]
    assert store.enqueue_unwatched(100, timedelta(0)) == 0
    assert world.watch.list_topics(other) == []


def test_a_changed_topic_shows_its_recalculation_until_it_is_done(world: World) -> None:
    topic = world.watch.create_topic(world.context, name="IA", keywords=["IA"])
    assert topic.rescoring
    world.run_jobs()
    done = world.watch.get_topic(world.context, topic.id)
    assert done is not None and not done.rescoring and done.rescored_at is not None
    world.watch.update_topic(world.context, topic.id, name="IA", keywords=["IA", "robot"])
    assert world.watch.get_topic(world.context, topic.id).rescoring  # type: ignore[union-attr]
    world.run_jobs()
    assert not world.watch.get_topic(world.context, topic.id).rescoring  # type: ignore[union-attr]
    assert world.watch.rescore(world.context, topic.id)
    assert world.watch.get_topic(world.context, topic.id).rescoring  # type: ignore[union-attr]
    assert not world.watch.rescore(world.context, uuid.uuid4())


def test_refresh_collects_every_active_source_and_rescores_every_topic(world: World) -> None:
    world.source("a")
    world.source("b")
    world.watch.create_topic(world.context, name="IA", keywords=["IA"])
    world.queue.jobs.clear()
    assert world.watch.refresh(world.context) == (2, 1)
    assert sorted(name for name, _ in world.queue.jobs) == [
        "collection.collect_source",
        "collection.collect_source",
        RESCORE_TOPIC,
    ]
