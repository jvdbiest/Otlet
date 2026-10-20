# SPDX-License-Identifier: AGPL-3.0-or-later
"""The watch feed and its triage on a real PostgreSQL (X02, F-VEI-04, F-VEI-05)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
from otlet.watch.adapters.triage_postgres import PostgresTriageStore
from otlet.watch.application.triage import Change, Feed
from otlet.watch.domain.triage import Decision, View
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces
from otlet.workspaces.domain.model import Role, WorkspaceContext

pytestmark = requires_database

NOW = datetime.now(UTC)


def context_for(engine: sa.Engine, login: str) -> WorkspaceContext:
    user = Authentication(PostgresIdentityStore(engine), Argon2Hasher()).create_user(
        login, login, "une phrase de passe assez longue"
    )
    workspaces = Workspaces(PostgresWorkspaceStore(engine))
    context = workspaces.enter(user, workspaces.create(user, "Veille").id)
    assert context is not None
    return context


@dataclass
class Setup:
    engine: sa.Engine
    feed: Feed
    context: WorkspaceContext
    ids: list[uuid.UUID]


@pytest.fixture
def setup(migrated: TestDatabase) -> Setup:
    engine = db.create_engine(migrated.app_url)
    context = context_for(engine, "alice@example.org")
    store = PostgresCollectionStore(engine, lambda connection, name, **kwargs: 0)
    source = store.add_source(
        context.workspace_id,
        name="Journal",
        url="https://j.example.org/feed",
        feed_url="https://j.example.org/feed",
        site_url=None,
        interval_minutes=60,
    ).id
    entries = [
        NewItem(
            FeedEntry(
                guid=str(n),
                url=None,
                title=f"Article {n}",
                author=None,
                published_at=NOW - timedelta(hours=n),
                summary=None,
                content=None,
            ),
            TextStatus.SUMMARY_ONLY,
            "test",
        )
        for n in range(3)
    ]
    outcome = Outcome(fetched_at=NOW, next_fetch_at=NOW, success=True)
    store.finish_collection(context.workspace_id, source, outcome, entries)
    feed = Feed(PostgresTriageStore(engine))
    ids = [f.item.id for f in feed.feed(context, view=View.ALL)]
    return Setup(engine, feed, context, ids)


def titles(feed: Feed, context: WorkspaceContext, **kwargs: object) -> list[str]:
    return [f.item.title for f in feed.feed(context, **kwargs)]  # type: ignore[arg-type]


def test_keeping_and_dismissing_sort_the_feed(setup: Setup) -> None:
    feed, context, ids = setup.feed, setup.context, setup.ids
    assert titles(feed, context) == ["Article 0", "Article 1", "Article 2"]
    feed.change(context, ids[0], Change(decision=Decision.KEPT))
    feed.change(context, ids[1], Change(decision=Decision.DISMISSED))
    assert titles(feed, context) == ["Article 2"]
    assert titles(feed, context, view=View.KEPT) == ["Article 0"]
    assert titles(feed, context, view=View.DISMISSED) == ["Article 1"]
    # Back to sort.
    feed.change(context, ids[1], Change(clear_decision=True))
    assert titles(feed, context) == ["Article 1", "Article 2"]


def test_pinned_items_come_first_and_paging_follows(setup: Setup) -> None:
    feed, context, ids = setup.feed, setup.context, setup.ids
    feed.change(context, ids[2], Change(pinned=True))
    assert titles(feed, context) == ["Article 2", "Article 0", "Article 1"]
    assert titles(feed, context, view=View.PINNED) == ["Article 2"]
    first = feed.feed(context, limit=2)
    rest = feed.feed(context, limit=2, before=first[-1].item.id)
    assert [f.item.title for f in first + rest] == ["Article 2", "Article 0", "Article 1"]


def test_reading_marks_and_unread_filter(setup: Setup) -> None:
    feed, context, ids = setup.feed, setup.context, setup.ids
    triage = feed.change(context, ids[0], Change(read=True))
    assert triage is not None and triage.read and triage.decision is None
    assert titles(feed, context, unread_only=True) == ["Article 1", "Article 2"]
    again = feed.change(context, ids[0], Change(decision=Decision.KEPT))
    assert again is not None and again.read  # a decision keeps the reading
    unread = feed.change(context, ids[0], Change(read=False))
    assert unread is not None and not unread.read and unread.decision is Decision.KEPT


def test_triage_belongs_to_each_user_and_workspace(setup: Setup) -> None:
    engine, feed, context, ids = setup.engine, setup.feed, setup.context, setup.ids
    feed.change(context, ids[0], Change(decision=Decision.DISMISSED))
    stranger = context_for(engine, "bob@example.org")
    assert feed.feed(stranger, view=View.ALL) == []
    assert feed.change(stranger, ids[0], Change(decision=Decision.KEPT)) is None
    assert feed.triage(stranger, ids[0]) is None


def test_progress_counts_the_first_steps(setup: Setup) -> None:
    feed, context, ids = setup.feed, setup.context, setup.ids
    first = feed.progress(context)
    assert (first.sources, first.topics, first.decisions) == (1, 0, 0)
    feed.change(context, ids[0], Change(decision=Decision.KEPT))
    assert feed.progress(context).decisions == 1


def test_a_dismissed_item_leaves_its_topics(migrated: TestDatabase, setup: Setup) -> None:
    from otlet.watch.adapters.postgres import PostgresWatchStore
    from otlet.watch.application.watch import Watch

    feed, context, ids = setup.feed, setup.context, setup.ids
    watch = Watch(PostgresWatchStore(setup.engine, lambda connection, name, **kwargs: 0))
    topic = watch.create_topic(context, name="Articles", keywords=["article"])
    watch.rescore_topic(context.workspace_id, topic.id, NOW)
    assert len(watch.topic_items(context, topic.id, NOW, limit=10, offset=0)) == 3
    feed.change(context, ids[0], Change(decision=Decision.DISMISSED))
    feed.change(context, ids[1], Change(decision=Decision.KEPT))
    shown = watch.topic_items(context, topic.id, NOW, limit=10, offset=0)
    assert [(s.item.title, s.triage.decision) for s in shown] == [
        ("Article 1", Decision.KEPT),
        ("Article 2", None),
    ]


def test_search_results_carry_the_triage_of_the_user(setup: Setup) -> None:
    from otlet.watch.adapters.postgres import PostgresWatchStore
    from otlet.watch.application.watch import Watch

    feed, context, ids = setup.feed, setup.context, setup.ids
    watch = Watch(PostgresWatchStore(setup.engine, lambda connection, name, **kwargs: 0))
    feed.change(context, ids[0], Change(decision=Decision.KEPT, pinned=True))
    found = {f.item.title: f.triage for f in watch.search(context, "article")}
    assert found["Article 0"].decision is Decision.KEPT and found["Article 0"].pinned
    assert found["Article 1"].decision is None


def test_topics_filter_the_feed_and_the_search(setup: Setup) -> None:
    from otlet.watch.adapters.postgres import PostgresWatchStore
    from otlet.watch.application.watch import Watch
    from otlet.watch.domain.triage import TopicFilter

    feed, context = setup.feed, setup.context
    watch = Watch(PostgresWatchStore(setup.engine, lambda connection, name, **kwargs: 0))
    first = watch.create_topic(context, name="A", keywords=["0", "1"])
    second = watch.create_topic(context, name="B", keywords=["1", "2"])
    for topic in (first, second):
        watch.rescore_topic(context.workspace_id, topic.id, NOW)
    only_a = TopicFilter((first.id,))
    either = TopicFilter((first.id, second.id))
    both = TopicFilter((first.id, second.id), all_topics=True)
    assert titles(feed, context, topics=only_a) == ["Article 0", "Article 1"]
    assert titles(feed, context, topics=either) == ["Article 0", "Article 1", "Article 2"]
    assert titles(feed, context, topics=both) == ["Article 1"]
    searched = [f.item.title for f in watch.search(context, "article", topics=both)]
    assert searched == ["Article 1"]


def test_items_carry_their_topics_best_score_first(setup: Setup) -> None:
    from otlet.watch.adapters.postgres import PostgresWatchStore
    from otlet.watch.application.watch import Watch

    feed, context = setup.feed, setup.context
    watch = Watch(PostgresWatchStore(setup.engine, lambda connection, name, **kwargs: 0))
    topics = [
        watch.create_topic(context, name="B", keywords=["1", "2"]),
        watch.create_topic(context, name="A", keywords=["0", "1"]),
        # Two keywords found in "Article 1": its best score, so its main topic.
        watch.create_topic(context, name="C", keywords=["1", "article"]),
    ]
    for topic in topics:
        watch.rescore_topic(context.workspace_id, topic.id, NOW)
    tags = {f.item.title: [t.name for t in f.topics] for f in feed.feed(context)}
    # In "Article 1", A and B score the same: the name decides.
    assert tags == {"Article 0": ["A", "C"], "Article 1": ["C", "A", "B"], "Article 2": ["B", "C"]}
    second = next(f for f in feed.feed(context) if f.item.title == "Article 1")
    assert second.topics[0].id == topics[2].id
    assert second.topics[0].score > second.topics[1].score == second.topics[2].score
    found = {f.item.title: [t.name for t in f.topics] for f in watch.search(context, "article")}
    assert found == tags


def test_all_is_in_date_order_and_a_period_narrows_feed_and_search(setup: Setup) -> None:
    from otlet.watch.adapters.postgres import PostgresWatchStore
    from otlet.watch.application.watch import Watch
    from otlet.watch.domain.triage import Period

    feed, context, ids = setup.feed, setup.context, setup.ids
    feed.change(context, ids[2], Change(pinned=True))
    # « Tout »: the most recent first, pinned or not; the other views keep pinned items first.
    assert titles(feed, context, view=View.ALL) == ["Article 0", "Article 1", "Article 2"]
    assert titles(feed, context) == ["Article 2", "Article 0", "Article 1"]
    first = feed.feed(context, view=View.ALL, limit=1)[0]
    assert titles(feed, context, view=View.ALL, before=first.item.id) == ["Article 1", "Article 2"]
    recent = Period(since=NOW - timedelta(minutes=90))
    older = Period(until=NOW - timedelta(minutes=30))
    assert titles(feed, context, view=View.ALL, period=recent) == ["Article 0", "Article 1"]
    assert titles(feed, context, view=View.ALL, period=older) == ["Article 1", "Article 2"]
    watch = Watch(PostgresWatchStore(setup.engine, lambda connection, name, **kwargs: 0))
    found = {f.item.title for f in watch.search(context, "article", period=older)}
    assert found == {"Article 1", "Article 2"}
    assert not Period(since=NOW, until=NOW).valid


def test_a_change_applies_to_several_items_at_once(setup: Setup) -> None:
    feed, context, ids = setup.feed, setup.context, setup.ids
    assert (
        feed.change_many(context, [ids[0], ids[1], uuid.uuid4()], Change(decision=Decision.KEPT))
        == 2
    )
    assert titles(feed, context, view=View.KEPT) == ["Article 0", "Article 1"]
    assert titles(feed, context) == ["Article 2"]
    assert feed.change_many(context, ids[:2], Change(clear_decision=True)) == 2
    assert titles(feed, context) == ["Article 0", "Article 1", "Article 2"]
    other = context_for(setup.engine, "bob@example.org")
    assert feed.change_many(other, ids, Change(pinned=True)) == 0
    # « Tout sélectionner » takes every item of the filters, not one page (Joël, 2026-10-20).
    assert set(feed.ids(context, view=View.ALL)) == set(ids)
    feed.change_many(context, [ids[2]], Change(decision=Decision.KEPT))
    assert set(feed.ids(context)) == {ids[0], ids[1]}
    assert feed.ids(other, view=View.ALL) == []


def test_an_archived_item_leaves_the_current_views(setup: Setup) -> None:
    feed, context, ids = setup.feed, setup.context, setup.ids
    feed.change(context, ids[0], Change(decision=Decision.KEPT))
    feed.change_many(context, [ids[0], ids[1]], Change(decision=Decision.ARCHIVED))
    assert titles(feed, context, view=View.ARCHIVED) == ["Article 0", "Article 1"]
    assert titles(feed, context) == ["Article 2"]
    assert titles(feed, context, view=View.KEPT) == []
    assert len(titles(feed, context, view=View.ALL)) == 3
    feed.change(context, ids[0], Change(clear_decision=True))
    assert titles(feed, context) == ["Article 0", "Article 2"]


def test_the_feed_sorts_and_groups_by_score_topic_and_source(setup: Setup) -> None:
    from otlet.watch.adapters.postgres import PostgresWatchStore
    from otlet.watch.application.watch import Watch
    from otlet.watch.domain.triage import GroupBy, InGroup, Sort

    feed, context, ids = setup.feed, setup.context, setup.ids
    store = PostgresCollectionStore(setup.engine, lambda connection, name, **kwargs: 0)
    agency = store.add_source(
        context.workspace_id,
        name="agence",  # lower case: the order of names ignores the case
        url="https://a.example.org/feed",
        feed_url="https://a.example.org/feed",
        site_url=None,
        interval_minutes=60,
    ).id
    entry = FeedEntry(
        guid="9",
        url=None,
        title="Dépêche 9",
        author=None,
        published_at=NOW - timedelta(hours=4),
        summary=None,
        content=None,
    )
    store.finish_collection(
        context.workspace_id,
        agency,
        Outcome(fetched_at=NOW, next_fetch_at=NOW, success=True),
        [NewItem(entry, TextStatus.SUMMARY_ONLY, "test")],
    )
    watch = Watch(PostgresWatchStore(setup.engine, lambda connection, name, **kwargs: 0))
    topics = {
        name: watch.create_topic(context, name=name, keywords=keywords)
        for name, keywords in (("B", ["1", "2"]), ("A", ["0", "1"]), ("C", ["1", "article"]))
    }
    for topic in topics.values():
        watch.rescore_topic(context.workspace_id, topic.id, NOW)
    # Main topics: Article 0 → A, Article 1 → C (best score), Article 2 → B; the dispatch: none.
    items = feed.feed(context, view=View.ALL)
    by_score = sorted(
        items,
        key=lambda f: (
            -(f.topics[0].score if f.topics else -1),
            NOW - (f.item.published_at or NOW),
        ),
    )
    assert titles(feed, context, view=View.ALL, sort=Sort.SCORE) == [f.item.title for f in by_score]
    assert by_score[0].item.title == "Article 1"
    in_topics = ["Article 0", "Article 2", "Article 1", "Dépêche 9"]
    assert titles(feed, context, view=View.ALL, sort=Sort.TOPIC) == in_topics
    in_sources = ["Dépêche 9", "Article 0", "Article 1", "Article 2"]
    assert titles(feed, context, view=View.ALL, sort=Sort.SOURCE) == in_sources
    # The cursor follows the sort, page after page.
    for sort, expected in ((Sort.TOPIC, in_topics), (Sort.SOURCE, in_sources)):
        seen: list[str] = []
        before = None
        while page := feed.feed(context, view=View.ALL, sort=sort, limit=1, before=before):
            seen.append(page[0].item.title)
            before = page[0].item.id
        assert seen == expected
    # Pinned items stay first in the views that pin them, whatever the sort.
    feed.change(context, ids[2], Change(pinned=True))
    pinned_first = ["Article 2", "Article 0", "Article 1", "Dépêche 9"]
    assert titles(feed, context, sort=Sort.TOPIC) == pinned_first
    first = feed.feed(context, sort=Sort.TOPIC, limit=1)[0]
    assert titles(feed, context, sort=Sort.TOPIC, before=first.item.id) == pinned_first[1:]
    # Groups: alphabetical, the one without key last, counted with the filters of the feed.
    groups = feed.groups(context, by=GroupBy.TOPIC, view=View.ALL)
    assert [(g.key, g.name, g.count) for g in groups] == [
        (topics["A"].id, "A", 1),
        (topics["B"].id, "B", 1),
        (topics["C"].id, "C", 1),
        (None, "", 1),
    ]
    sources = feed.groups(context, by=GroupBy.SOURCE, view=View.ALL)
    assert [(g.name, g.count) for g in sources] == [("agence", 1), ("Journal", 3)]
    feed.change(context, ids[0], Change(decision=Decision.DISMISSED))
    sources = feed.groups(context, by=GroupBy.SOURCE)
    assert [(g.name, g.count) for g in sources] == [("agence", 1), ("Journal", 2)]
    # One group of the feed, in the order of the sort.
    alone = InGroup(GroupBy.TOPIC, None)
    assert titles(feed, context, view=View.ALL, group=alone) == ["Dépêche 9"]
    journal = InGroup(GroupBy.SOURCE, sources[1].key)
    assert titles(feed, context, group=journal) == ["Article 2", "Article 1"]


def test_the_owner_purges_the_archived_items_no_brief_holds(setup: Setup) -> None:
    """Joël, 2026-10-20: « Supprimer définitivement » in Archivés; an item a brief holds stays,
    an item not archived stays, and a deleted item of a feed is not collected again."""
    feed, context, ids = setup.feed, setup.context, setup.ids
    feed.change_many(context, ids[:2], Change(decision=Decision.ARCHIVED))
    with db.workspace_transaction(setup.engine, context.workspace_id) as connection:
        brief = connection.execute(
            sa.text(
                "INSERT INTO briefs (id, workspace_id, created_by, title)"
                " VALUES (gen_random_uuid(), :w, :u, 'Brief') RETURNING id"
            ),
            {"w": context.workspace_id, "u": context.user_id},
        ).scalar_one()
        connection.execute(
            sa.text(
                "INSERT INTO brief_items (workspace_id, brief_id, item_id, position)"
                " VALUES (:w, :b, :i, 0)"
            ),
            {"w": context.workspace_id, "b": brief, "i": ids[1]},
        )
    guest = WorkspaceContext(context.user_id, context.workspace_id, Role.EDITOR)
    with pytest.raises(PermissionError):
        feed.purge_archived(guest, ids)
    purged = feed.purge_archived(context, ids)
    assert (purged.deleted, purged.kept) == (1, 1)
    assert set(feed.ids(context, view=View.ALL)) == {ids[1], ids[2]}
    with db.workspace_transaction(setup.engine, context.workspace_id) as connection:
        removed = connection.execute(sa.text("SELECT count(*) FROM removed_items")).scalar_one()
    assert removed == 1
