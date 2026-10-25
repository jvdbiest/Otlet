# SPDX-License-Identifier: AGPL-3.0-or-later
"""A conversation of the Reporter on a real PostgreSQL, with a fake model (ADR-0044)."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.assistant.application.assistant import Assistant
from otlet.assistant.application.dossiers import Asked
from otlet.assistant.domain.terms import Concept
from otlet.collection.adapters.postgres import PostgresCollectionStore
from otlet.collection.application.ports import NewItem, Outcome
from otlet.collection.domain.model import FeedEntry, TextStatus
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.reporter.adapters.postgres import PostgresReporterStore
from otlet.reporter.application.reporter import Reporter, ReporterError
from otlet.reporter.domain.facts import Agreement
from otlet.reporter.domain.questions import Operation
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces
from otlet.workspaces.domain.model import WorkspaceContext

pytestmark = requires_database

NOW = datetime.now(UTC)

AUSTEN = [
    ("Tempête Austen : quatre blessés à Bruxelles", "Quatre personnes ont été blessées.", 1),
    ("Tempête Austen : la côte en alerte", "Des rafales à 110 km/h à la côte.", 1),
    ("Storm Austen: vier gewonden in Brussel", "Vier gewonden in Brussel.", 1),
]


def context_for(engine: sa.Engine, login: str) -> WorkspaceContext:
    user = Authentication(PostgresIdentityStore(engine), Argon2Hasher()).create_user(
        login, login, "une phrase de passe assez longue"
    )
    workspaces = Workspaces(PostgresWorkspaceStore(engine))
    context = workspaces.enter(user, workspaces.create(user, "Veille").id)
    assert context is not None
    return context


def collect(
    engine: sa.Engine,
    context: WorkspaceContext,
    source: str,
    language: str,
    items: list[tuple[str, str, int]],
) -> None:
    """Items (title, summary, age in days) of one feed, in one language."""
    store = PostgresCollectionStore(engine, lambda connection, name, **kwargs: 0)
    source_id = store.add_source(
        context.workspace_id,
        name=source,
        url=f"https://{source}.example.be/feed",
        feed_url=f"https://{source}.example.be/feed",
        site_url=None,
        interval_minutes=60,
    ).id
    entries = [
        NewItem(
            FeedEntry(
                guid=title,
                url=f"https://{source}.example.be/{n}",
                title=title,
                author=None,
                published_at=NOW - timedelta(days=days),
                summary=summary,
                content=None,
                language=language,
            ),
            TextStatus.SUMMARY_ONLY,
            "test",
        )
        for n, (title, summary, days) in enumerate(items)
    ]
    outcome = Outcome(fetched_at=NOW, next_fetch_at=NOW, success=True)
    store.finish_collection(context.workspace_id, source_id, outcome, entries)


class FakeModel:
    """Answers each question as the bench did, by the words of the question."""

    def __init__(self) -> None:
        self.asked: list[str] = []
        self.fail = False

    def ask(self, user_id: UUID, system: str, user: str, *args: Any) -> Asked:
        self.asked.append(user)
        if self.fail:
            return Asked(None, "no model", None, ())
        question = user.rsplit("Question : ", 1)[-1].split("\n")[0]
        if "Dernière question : " in user:
            question = user.rsplit("Dernière question : ", 1)[-1]
            return Asked(json.dumps(self._operation(question)), None, "fake", ())
        lines = []
        for n, block in enumerate(user.split("Articles :", 1)[-1].split("\n[")[1:], 1):
            if "blessés à Bruxelles" in block:
                lines.append(self._line(n, "quatre", "Quatre personnes ont été blessées."))
            if "gewonden" in block:
                lines.append(self._line(n, "vier", "Vier gewonden in Brussel."))
        lines.append(self._line(1, "12", "Douze personnes."))  # not in the article
        return Asked(json.dumps({"lignes": lines, "conclusion": question}), None, "fake", ())

    @staticmethod
    def _operation(question: str) -> dict[str, Any]:
        if "Austen" in question:
            # A concept the question never named is added, as the model did on the bench.
            concepts = [
                {"name": "Austen", "terms": ["Austen", "tempête Austen"]},
                {"name": "impact", "terms": ["impact", "effet"]},
            ]
            return {"operation": "chercher", "concepts": concepts, "langue": "toutes"}
        if "néerlandais" in question:
            return {"operation": "chercher", "concepts": [{"name": "nl", "terms": ["nl"]}]}
        if "Bruxelles" in question:
            concepts = [{"name": "Bruxelles", "terms": ["Bruxelles", "Brussel"]}]
            return {"operation": "restreindre", "concepts": concepts}
        return {"operation": "fait", "concepts": []}

    @staticmethod
    def _line(article: int, figure: str, passage: str) -> dict[str, Any]:
        return {
            "article": article,
            "chiffre": figure,
            "mesure": "blessés",
            "quand": "vendredi",
            "ou": "Bruxelles",
            "extrait": passage,
        }


@pytest.fixture
def reporter(migrated: TestDatabase) -> tuple[Reporter, Reporter, WorkspaceContext, sa.Engine]:
    engine = db.create_engine(migrated.app_url)
    context = context_for(engine, "alice@example.org")
    collect(engine, context, "ladh", "fr", AUSTEN[:2])
    collect(engine, context, "bruzz", "nl", AUSTEN[2:])
    Assistant(PostgresAssistantStore(engine)).add_entry(context, ["Bruxelles", "Brussel"])
    enqueued: list[dict[str, Any]] = []

    def enqueue(connection: sa.Connection, name: str, **kwargs: Any) -> int:
        enqueued.append(kwargs)
        return len(enqueued)

    store = PostgresReporterStore(engine, enqueue)
    search = PostgresAssistantStore(engine)
    api = Reporter(store, search)
    worker = Reporter(store, search, FakeModel())
    return api, worker, context, engine


def answer(worker: Reporter, context: WorkspaceContext, conversation: UUID, turn: UUID) -> None:
    worker.run(context.workspace_id, context.user_id, conversation, turn)


def test_a_conversation_finds_restricts_and_answers_a_fact(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, worker, context, _ = reporter
    conversation = api.start(context, "Les articles sur la tempête Austen")
    first = conversation.turns[0]
    assert first.status == "pending"
    with pytest.raises(ReporterError) as refused:
        api.ask(context, conversation.id, "Lesquels concernent Bruxelles ?")
    assert refused.value.code == "turn_pending"
    answer(worker, context, conversation.id, first.id)
    found = api.get(context, conversation.id)
    assert found is not None
    turn = found.turns[0]
    assert (turn.status, turn.operation) == ("done", Operation.CHERCHER)
    # The concept « impact » the question never named is dropped; « toutes » is no language.
    assert [w.concept.name for w in turn.concepts] == ["Austen"]
    assert turn.state.language is None
    assert len(turn.candidates) == 3

    second = api.ask(context, conversation.id, "Lesquels concernent Bruxelles ?")
    answer(worker, context, conversation.id, second.id)
    third = api.ask(context, conversation.id, "Et en néerlandais ?")
    answer(worker, context, conversation.id, third.id)
    found = api.get(context, conversation.id)
    assert found is not None
    restricted, dutch = found.turns[1], found.turns[2]
    assert {c.title for c in restricted.candidates} == {AUSTEN[0][0], AUSTEN[2][0]}
    # A language asked is a filter, never a concept.
    assert dutch.operation is Operation.RESTREINDRE
    assert [w.concept.name for w in dutch.concepts] == ["Austen", "Bruxelles"]
    assert [c.title for c in dutch.candidates] == [AUSTEN[2][0]]


def test_a_fact_is_cited_by_source_and_compared_without_a_model(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, worker, context, _ = reporter
    conversation = api.start(context, "Les articles sur la tempête Austen")
    answer(worker, context, conversation.id, conversation.turns[0].id)
    turn = api.ask(context, conversation.id, "Combien de blessés ?")
    answer(worker, context, conversation.id, turn.id)
    found = api.get(context, conversation.id)
    assert found is not None
    fact = found.turns[1].fact
    assert fact is not None
    assert sorted(f.publisher for f in fact.lines) == ["bruzz", "ladh"]
    # « Douze personnes » is in no article: dropped. « quatre » and « vier » are the same
    # four injured, in two languages: the sources agree.
    assert fact.dropped == 1
    assert fact.agreement is Agreement.CONCORDENT
    assert [c.same for c in fact.compared] == [True]
    # The set is the one the question was asked on.
    assert len(found.turns[1].candidates) == 3


def test_the_author_changes_the_terms_without_a_model(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, worker, context, _ = reporter
    conversation = api.start(context, "Les articles sur la tempête Austen")
    turn = conversation.turns[0]
    answer(worker, context, conversation.id, turn.id)
    changed = api.set_terms(
        context, conversation.id, turn.id, [Concept("Austen", ("Austen",)), Concept("c", ("côte",))]
    )
    assert [c.title for c in changed.candidates] == [AUSTEN[1][0]]
    found = api.get(context, conversation.id)
    assert found is not None and [c.title for c in found.turns[0].candidates] == [AUSTEN[1][0]]


def test_a_question_the_model_cannot_translate(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    """With nothing yet, the question itself is searched; later, the turn fails."""
    api, worker, context, engine = reporter
    store = PostgresReporterStore(engine)
    failing = FakeModel()
    failing.fail = True
    down = Reporter(store, PostgresAssistantStore(engine), failing)
    conversation = api.start(context, "Austen")
    answer(down, context, conversation.id, conversation.turns[0].id)
    turn = api.ask(context, conversation.id, "Lesquels concernent Bruxelles ?")
    answer(down, context, conversation.id, turn.id)
    found = api.get(context, conversation.id)
    assert found is not None
    assert (found.turns[0].status, len(found.turns[0].candidates)) == ("done", 3)
    assert (found.turns[1].status, found.turns[1].error) == ("failed", "no model")
