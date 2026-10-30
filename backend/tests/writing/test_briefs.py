# SPDX-License-Identifier: AGPL-3.0-or-later
"""Briefs on a real PostgreSQL (U03, F-RED-01): built on items, which move to drafting."""

import uuid
from collections.abc import Sequence
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
from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.adapters.postgres import PostgresBriefStore
from otlet.writing.application.briefs import Briefs
from otlet.writing.domain.brief import BriefError, BriefFields, Length, Mode, ModelChoice, Nature

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


def collect(engine: sa.Engine, context: WorkspaceContext, source: str, titles: list[str]) -> None:
    store = PostgresCollectionStore(engine, lambda connection, name, **kwargs: 0)
    source_id = store.add_source(
        context.workspace_id,
        name=source,
        url=f"https://{source}.example.org/feed",
        feed_url=f"https://{source}.example.org/feed",
        site_url=None,
        interval_minutes=60,
    ).id
    entries = [
        NewItem(
            FeedEntry(
                guid=title,
                url=None,
                title=title,
                author=None,
                published_at=NOW - timedelta(hours=n),
                summary=None,
                content=None,
            ),
            TextStatus.SUMMARY_ONLY,
            "test",
        )
        for n, title in enumerate(titles)
    ]
    outcome = Outcome(fetched_at=NOW, next_fetch_at=NOW, success=True)
    store.finish_collection(context.workspace_id, source_id, outcome, entries)


@dataclass
class Setup:
    engine: sa.Engine
    feed: Feed
    briefs: Briefs
    context: WorkspaceContext
    ids: dict[str, uuid.UUID]
    checked: list[ModelChoice]


@pytest.fixture
def setup(migrated: TestDatabase) -> Setup:
    engine = db.create_engine(migrated.app_url)
    context = context_for(engine, "alice@example.org")
    collect(engine, context, "journal", ["Article A", "Article B"])
    collect(engine, context, "agence", ["Dépêche C"])
    feed = Feed(PostgresTriageStore(engine))
    ids = {f.item.title: f.item.id for f in feed.feed(context, view=View.ALL)}
    feed.change_many(context, list(ids.values()), Change(decision=Decision.KEPT))
    checked: list[ModelChoice] = []

    def mark(context: WorkspaceContext, item_ids: Sequence[uuid.UUID]) -> None:
        feed.change_many(context, list(item_ids), Change(decision=Decision.WRITING))

    def check(user_id: uuid.UUID, choice: ModelChoice) -> None:
        checked.append(choice)
        if choice.model == "blocked":
            raise BriefError("model_blocked", "blocked by the instance")

    briefs = Briefs(PostgresBriefStore(engine), mark, check)
    return Setup(engine, feed, briefs, context, ids, checked)


def titles(feed: Feed, context: WorkspaceContext, view: View) -> list[str]:
    return [f.item.title for f in feed.feed(context, view=view)]


def test_a_brief_moves_its_items_to_drafting(setup: Setup) -> None:
    briefs, context, ids = setup.briefs, setup.context, setup.ids
    brief = briefs.create(
        context,
        BriefFields(
            title="  La veille libre  ",
            item_ids=(ids["Article B"], ids["Article A"], ids["Article A"]),
            angle="Mon expérience de six mois",
            instructions="  Relie-les.  ",
            length=Length.SHORT,
        ),
    )
    assert brief.fields.title == "La veille libre"
    assert brief.fields.instructions == "Relie-les."
    assert [item.title for item in brief.items] == ["Article B", "Article A"]
    assert brief.items[0].source_name == "journal"
    assert brief.fields.model is None  # the profile of the author
    assert (brief.sources, brief.single_source) == (1, True)
    assert titles(setup.feed, context, View.WRITING) == ["Article A", "Article B"]
    assert titles(setup.feed, context, View.KEPT) == ["Dépêche C"]
    # Adding an item of another source: two sources, and that item moves too.
    fields = BriefFields(
        title="La veille libre",
        item_ids=(ids["Article B"], ids["Dépêche C"]),
        angle=brief.fields.angle,
    )
    updated = briefs.update(context, brief.id, fields)
    assert updated is not None
    assert [item.title for item in updated.items] == ["Article B", "Dépêche C"]
    assert (updated.sources, updated.single_source) == (2, False)
    assert titles(setup.feed, context, View.KEPT) == []
    assert [b.id for b in briefs.list(context)] == [brief.id]
    # Removed from its brief, or with the brief deleted, an item stays in drafting.
    assert briefs.delete(context, brief.id)
    assert briefs.get(context, brief.id) is None
    assert len(titles(setup.feed, context, View.WRITING)) == 3
    assert not briefs.delete(context, brief.id)


def test_the_fields_of_a_brief_are_checked(setup: Setup) -> None:
    briefs, context, ids = setup.briefs, setup.context, setup.ids
    item = (ids["Article A"],)
    cases = {
        "invalid_title": BriefFields(title="  ", item_ids=item),
        "invalid_items": BriefFields(title="T", item_ids=()),
        "invalid_language": BriefFields(title="T", item_ids=item, language="xx"),
        "invalid_angle": BriefFields(title="T", item_ids=item, angle="a" * 4001),
        "invalid_instructions": BriefFields(title="T", item_ids=item, instructions="a" * 2001),
        # The audience, tone and channel are keys of closed lists (Joël, 2026-10-19).
        "invalid_audience": BriefFields(title="T", item_ids=item, audience="Motards"),
        "invalid_tone": BriefFields(title="T", item_ids=item, tone="Professionnel"),
        "invalid_channel": BriefFields(title="T", item_ids=item, channel="TikTok"),
        "unknown_item": BriefFields(title="T", item_ids=(uuid.uuid4(),)),
        "model_blocked": BriefFields(
            title="T", item_ids=item, model=ModelChoice(uuid.uuid4(), "blocked")
        ),
        # Checked by the database: the provider is not one of the author's.
        "unknown_provider": BriefFields(
            title="T", item_ids=item, model=ModelChoice(uuid.uuid4(), "qwen2.5:1.5b-instruct")
        ),
    }
    for code, fields in cases.items():
        with pytest.raises(BriefError) as caught:
            briefs.create(context, fields)
        assert caught.value.code == code
    assert briefs.list(context) == []
    assert titles(setup.feed, context, View.WRITING) == []


def test_a_brief_belongs_to_its_workspace(setup: Setup) -> None:
    briefs, context, ids = setup.briefs, setup.context, setup.ids
    brief = briefs.create(context, BriefFields(title="T", item_ids=(ids["Article A"],)))
    other = context_for(setup.engine, "bob@example.org")
    assert briefs.list(other) == []
    assert briefs.get(other, brief.id) is None
    assert (
        briefs.update(other, brief.id, BriefFields(title="X", item_ids=(ids["Article A"],))) is None
    )
    assert not briefs.delete(other, brief.id)
    with pytest.raises(BriefError) as caught:  # an item of another workspace
        briefs.create(other, BriefFields(title="T", item_ids=(ids["Article A"],)))
    assert caught.value.code == "unknown_item"


def test_the_matter_of_a_brief_being_written(setup: Setup) -> None:
    """Judged on the items of the workspace, saved or not (ADR-0041); the nature is kept."""
    briefs, context, ids = setup.briefs, setup.context, setup.ids
    stranger = context_for(setup.engine, "bob@example.org")
    collect(setup.engine, stranger, "ailleurs", ["Autre E"])
    other = next(iter(setup.feed.feed(stranger, view=View.ALL))).item.id
    chosen = [ids["Article A"], ids["Article B"], ids["Dépêche C"], other]
    evaluation = briefs.matter(context, chosen, Length.SHORT, Mode.SYNTHESIS, Nature.NEWS)
    values = {c.name: c.value for c in evaluation.criteria}
    # The item of another workspace is not found; two feeds, two publishers.
    assert (values["sources"], values["publishers"], values["freshness"]) == (3, 2, 0)
    assert (evaluation.level, evaluation.reason) == ("insufficient", "words")  # titles only
    brief = briefs.create(
        context,
        BriefFields(title="Fond", item_ids=(ids["Article A"],), nature=Nature.BACKGROUND),
    )
    assert brief.fields.nature is Nature.BACKGROUND
    loaded = briefs.get(context, brief.id)
    assert loaded is not None and loaded.fields.nature is Nature.BACKGROUND


def test_a_brief_keeps_the_verified_facts_and_its_conversation(setup: Setup) -> None:
    """ADR-0044 §10: the lines of a fact of the Reporter go with the brief, and their source."""
    from otlet.writing.domain.brief import VerifiedFact

    briefs, context, ids = setup.briefs, setup.context, setup.ids
    fact = VerifiedFact(ids["Article A"], "journal", "6,3 milliards", "volés", passage="Volés.")
    brief = briefs.create(
        context, BriefFields(title="Binance", item_ids=(ids["Article A"],), facts=(fact,))
    )
    found = briefs.get(context, brief.id)
    assert found is not None and found.fields.facts == (fact,)
    assert found.fields.conversation_id is None
    # A figure is checked against the text it comes from: its source is in the brief.
    other = VerifiedFact(ids["Article B"], "journal", "12")
    with pytest.raises(BriefError) as refused:
        briefs.create(context, BriefFields(title="X", item_ids=(ids["Article A"],), facts=(other,)))
    assert refused.value.code == "invalid_facts"
