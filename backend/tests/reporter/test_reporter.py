# SPDX-License-Identifier: AGPL-3.0-or-later
"""A conversation of the Reporter on a real PostgreSQL, with a fake model (ADR-0044)."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.assistant.application.assistant import Assistant
from otlet.assistant.application.dossiers import Asked
from otlet.assistant.domain.qualify import Judged, Verdict
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
from otlet.reporter.domain.reading import Coverage
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
        if "Question à vérifier : " in user:
            return Asked(json.dumps(self._reading(user)), None, "fake", ())
        if "Dernière question : " in user:
            question = user.rsplit("Dernière question : ", 1)[-1]
            if "pas encore d'ensemble" in question:
                concepts = [{"name": "Austen", "terms": ["Austen"]}]
                answer = {"operation": "chercher", "concepts": concepts}
                return Asked(json.dumps(answer), None, "fake", ())
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
        if "Austen" in question and "Combien" not in question:
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
    def _reading(user: str) -> dict[str, Any]:
        """Only the item on the injured in Brussels answers; the coast is searched next."""
        blocks = user.split("Articles :", 1)[-1].split("\n[")[1:]
        answers = [
            {"article": n, "raison": "les blessés"}
            for n, block in enumerate(blocks, 1)
            if "blessés à Bruxelles" in block
        ]
        return {
            "repondent": answers,
            "couverture": "partiel",
            "manque": "Le nombre de blessés à la côte manque.",
            "autres_concepts": [{"name": "côte", "terms": ["côte"]}],
        }

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
    """The turn fails and says why; the author asks again."""
    api, _, context, engine = reporter
    store = PostgresReporterStore(engine)
    failing = FakeModel()
    failing.fail = True
    down = Reporter(store, PostgresAssistantStore(engine), failing)
    conversation = api.start(context, "Austen")
    answer(down, context, conversation.id, conversation.turns[0].id)
    found = api.get(context, conversation.id)
    assert found is not None
    assert (found.turns[0].status, found.turns[0].error) == ("failed", "no model")
    # One attempt only when the model is down; twice when it ran out of room.
    assert len(failing.asked) == 1


def test_a_fact_asked_first_searches_then_reads(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    """« Quels sont les derniers faits concernant l'enseignement ? » found nothing: there was no
    set yet (Joël, 2026-10-29). The set is searched first, then the fact read in it."""
    api, worker, context, _ = reporter
    conversation = api.start(context, "Combien de blessés pendant la tempête Austen ?")
    answer(worker, context, conversation.id, conversation.turns[0].id)
    found = api.get(context, conversation.id)
    assert found is not None
    turn = found.turns[0]
    assert turn.operation is Operation.FAIT
    assert [w.concept.name for w in turn.concepts] == ["Austen"]
    assert len(turn.candidates) == 3
    assert turn.fact is not None and len(turn.fact.lines) == 2


def test_a_set_is_read_when_asked_and_once(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    """« Vérifier en lisant » (Joël, 2026-10-29): the model says which items truly answer and
    what is missing; one more search with its terms, without the items already read."""
    api, worker, context, _ = reporter
    conversation = api.start(context, "Les articles sur la tempête Austen")
    turn = conversation.turns[0]
    answer(worker, context, conversation.id, turn.id)
    pending = api.read_set(context, conversation.id, turn.id)
    assert pending.status == "pending" and pending.reading is not None
    assert pending.reading.requested
    answer(worker, context, conversation.id, turn.id)
    found = api.get(context, conversation.id)
    assert found is not None
    read = found.turns[0]
    assert read.status == "done" and read.reading is not None
    reading = read.reading
    assert not reading.requested
    assert [a.title for a in reading.answers] == [AUSTEN[0][0]]
    assert reading.coverage is Coverage.PARTIEL
    assert reading.missing == "Le nombre de blessés à la côte manque."
    # The second search found only the coast, already read: nothing more to read.
    assert [len(r.read) for r in reading.rounds] == [3, 0]
    assert [c.name for c in reading.rounds[1].concepts] == ["côte"]
    # The set and the answer stay as they were.
    assert len(read.candidates) == 3 and read.operation is Operation.CHERCHER
    with pytest.raises(ReporterError) as refused:
        api.read_set(context, conversation.id, turn.id)
    assert refused.value.code == "already_read"


def test_a_question_asked_to_be_read_is_read_before_it_is_shown(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, worker, context, _ = reporter
    conversation = api.start(context, "Les articles sur la tempête Austen", read=True)
    answer(worker, context, conversation.id, conversation.turns[0].id)
    found = api.get(context, conversation.id)
    assert found is not None
    turn = found.turns[0]
    assert turn.status == "done" and turn.reading is not None
    assert [a.title for a in turn.reading.answers] == [AUSTEN[0][0]]


def test_the_meaning_adds_the_items_the_words_miss(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    """ADR-0045: the items closest to the question join the items of its words; a restriction
    asked after applies to them too."""
    from otlet.meaning.adapters.postgres import literal
    from otlet.meaning.domain.meaning import DIMENSIONS, MODEL

    api, _, context, engine = reporter
    collect(engine, context, "vrt", "nl", [("Zware storm aan de kust", "Rukwinden.", 1)])
    close = [1.0] + [0.0] * (DIMENSIONS - 1)
    far = [0.0, 1.0] + [0.0] * (DIMENSIONS - 2)
    with db.workspace_transaction(engine, context.workspace_id) as connection:
        for title in [a[0] for a in AUSTEN] + ["Zware storm aan de kust"]:
            vector = close if title == "Zware storm aan de kust" else far
            connection.execute(
                sa.text(
                    "UPDATE source_items SET meaning = CAST(:v AS vector), meaning_model = :m"
                    " WHERE title = :t"
                ),
                {"v": literal(vector), "m": MODEL, "t": title},
            )
    worker = Reporter(
        PostgresReporterStore(engine, lambda connection, name, **kwargs: 0),
        PostgresAssistantStore(engine),
        FakeModel(),
        encode=lambda question: close,
    )
    conversation = api.start(context, "Les articles sur la tempête Austen")
    answer(worker, context, conversation.id, conversation.turns[0].id)
    found = api.get(context, conversation.id)
    assert found is not None
    titles = {c.title for c in found.turns[0].candidates}
    assert titles == {a[0] for a in AUSTEN} | {"Zware storm aan de kust"}
    assert found.turns[0].state.subject == 1 and len(found.turns[0].state.meaning) == DIMENSIONS
    # « Bruxelles » restricts the items of the meaning as well.
    turn = api.ask(context, conversation.id, "Lesquels concernent Bruxelles ?")
    answer(worker, context, conversation.id, turn.id)
    found = api.get(context, conversation.id)
    assert found is not None
    assert {c.title for c in found.turns[1].candidates} == {AUSTEN[0][0], AUSTEN[2][0]}
    # The terms changed by the author keep the meaning, without a model in the API.
    changed = api.set_terms(
        context, conversation.id, turn.id, [Concept("Austen", ("Austen",)), Concept("c", ("kust",))]
    )
    assert "Zware storm aan de kust" in {c.title for c in changed.candidates}


def test_a_question_is_cancelled_and_its_late_answer_is_not_kept(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, worker, context, _ = reporter
    conversation = api.start(context, "Les articles sur la tempête Austen")
    turn = conversation.turns[0]
    assert [t.question for t in api.running(context)] == [turn.question]
    cancelled = api.cancel(context, conversation.id)
    assert cancelled is not None
    assert (cancelled.turns[0].status, cancelled.turns[0].error) == ("failed", "cancelled")
    assert api.running(context) == []
    # The job that was waiting finds it cancelled, and asks no model.
    answer(worker, context, conversation.id, turn.id)
    found = api.get(context, conversation.id)
    assert found is not None and found.turns[0].status == "failed"
    # The conversation goes on.
    next_one = api.ask(context, conversation.id, "Les articles sur la tempête Austen")
    answer(worker, context, conversation.id, next_one.id)
    found = api.get(context, conversation.id)
    assert found is not None and found.turns[1].status == "done"


def test_a_reading_cancelled_leaves_the_answer_as_it_was(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, worker, context, _ = reporter
    conversation = api.start(context, "Les articles sur la tempête Austen")
    turn = conversation.turns[0]
    answer(worker, context, conversation.id, turn.id)
    api.read_set(context, conversation.id, turn.id)
    cancelled = api.cancel(context, conversation.id)
    assert cancelled is not None
    ended = cancelled.turns[0]
    assert (ended.status, ended.reading, len(ended.candidates)) == ("done", None, 3)
    found = api.get(context, conversation.id)
    assert found is not None and found.turns[0].status == "done"


def test_the_articles_of_today_keep_the_subject_and_the_sort(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    """Intempéries, « Trie-les », « Les articles d'aujourd'hui ? » (Joël, 2026-10-30)."""
    api, worker, context, engine = reporter
    collect(engine, context, "rtbf", "fr", [("Tempête Austen : ce matin", "Encore du vent.", 0)])
    store = PostgresReporterStore(engine)
    conversation = api.start(context, "Les articles sur la tempête Austen")
    first = conversation.turns[0]
    answer(worker, context, conversation.id, first.id)
    found = api.get(context, conversation.id)
    assert found is not None and len(found.turns[0].candidates) == 4
    today = next(c for c in found.turns[0].candidates if c.title == "Tempête Austen : ce matin")
    aside = Judged(Verdict.HORS_SUJET, "sans lien", True)
    store.save_turn(
        context.workspace_id,
        conversation.id,
        replace(found.turns[0], verdicts={c.id: aside for c in found.turns[0].candidates}),
    )
    turn = api.ask(context, conversation.id, "Les articles d'aujourd'hui ?")
    answer(worker, context, conversation.id, turn.id)
    found = api.get(context, conversation.id)
    assert found is not None
    last = found.turns[1]
    assert (last.operation, last.state.days) == (Operation.RESTREINDRE, 1)
    assert [w.concept.name for w in last.concepts] == ["Austen"]
    assert [c.title for c in last.candidates] == [today.title]
    assert last.verdicts == {today.id: aside}


def test_a_subject_taken_out_stays_out_without_a_model(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, _, context, engine = reporter
    model = FakeModel()
    worker = Reporter(PostgresReporterStore(engine), PostgresAssistantStore(engine), model)
    conversation = api.start(context, "Les articles sur la tempête Austen")
    answer(worker, context, conversation.id, conversation.turns[0].id)
    asked = len(model.asked)
    turn = api.ask(context, conversation.id, "En supprimant ce qui concerne la côte")
    answer(worker, context, conversation.id, turn.id)
    found = api.get(context, conversation.id)
    assert found is not None
    last = found.turns[1]
    assert (last.operation, last.state.excluded) == (Operation.EXCLURE, ("cote",))
    assert {c.title for c in last.candidates} == {AUSTEN[0][0], AUSTEN[2][0]}
    assert len(model.asked) == asked
    # The next question keeps it out.
    again = api.ask(context, conversation.id, "Et en néerlandais ?")
    answer(worker, context, conversation.id, again.id)
    found = api.get(context, conversation.id)
    assert found is not None and found.turns[2].state.excluded == ("cote",)


def test_dates_chosen_or_named_bound_the_set_and_trie_les_sorts_without_translation(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, worker, context, engine = reporter
    collect(engine, context, "rtbf", "fr", [("Tempête Austen : ce matin", "Encore du vent.", 0)])
    today = NOW.date()
    # On the calendar, with the first question.
    chosen = api.start(context, "Les articles sur la tempête Austen", dates=(today, today))
    answer(worker, context, chosen.id, chosen.turns[0].id)
    found = api.get(context, chosen.id)
    assert found is not None
    assert [c.title for c in found.turns[0].candidates] == ["Tempête Austen : ce matin"]
    assert found.turns[0].state.date_from == today
    # Named in a question, on a set found without dates.
    conversation = api.start(context, "Les articles sur la tempête Austen")
    answer(worker, context, conversation.id, conversation.turns[0].id)
    named = f"{today.day:02d}/{today.month:02d}/{today.year}"
    turn = api.ask(context, conversation.id, f"Uniquement les articles du {named}")
    answer(worker, context, conversation.id, turn.id)
    found = api.get(context, conversation.id)
    assert found is not None
    assert found.turns[1].operation is Operation.RESTREINDRE
    assert [c.title for c in found.turns[1].candidates] == ["Tempête Austen : ce matin"]
    assert [w.concept.name for w in found.turns[1].concepts] == ["Austen"]
    # « Trie-les » is a sort by its words: the model is only asked to sort.
    model = FakeModel()
    model.fail = True
    sorting = Reporter(PostgresReporterStore(engine), PostgresAssistantStore(engine), model)
    sort = api.ask(context, conversation.id, "Trie-les")
    answer(sorting, context, conversation.id, sort.id)
    found = api.get(context, conversation.id)
    assert found is not None and found.turns[2].operation is Operation.TRIER
    assert model.asked and not any("Dernière question : " in asked for asked in model.asked)


def test_conversations_are_deleted_by_their_author_only(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, worker, context, engine = reporter
    first = api.start(context, "Les articles sur la tempête Austen")
    answer(worker, context, first.id, first.turns[0].id)
    second = api.start(context, "Austen encore")
    kept = api.start(context, "Austen toujours")
    other = replace(context, user_id=context_for(engine, "bob@example.org").user_id)
    assert api.delete(other, [first.id]) == 0
    assert api.get(context, first.id) is not None
    # One answered, one being answered: the job of the second finds nothing to do.
    assert api.delete(context, [first.id, second.id]) == 2
    assert api.get(context, first.id) is None and api.get(context, second.id) is None
    answer(worker, context, second.id, second.turns[0].id)
    assert [c.id for c in api.recent(context)] == [kept.id]
    assert [t.conversation_id for t in api.running(context)] == [kept.id]


def test_the_news_of_the_day_are_the_articles_of_the_day(
    reporter: tuple[Reporter, Reporter, WorkspaceContext, sa.Engine],
) -> None:
    api, worker, context, engine = reporter
    collect(engine, context, "rtbf", "fr", [("Un article de ce matin", "Sur autre chose.", 0)])
    conversation = api.start(context, "Quelles-sont les actualités du jour ?")
    answer(worker, context, conversation.id, conversation.turns[0].id)
    found = api.get(context, conversation.id)
    assert found is not None
    turn = found.turns[0]
    assert (turn.status, turn.state.days, turn.concepts) == ("done", 1, [])
    assert [c.title for c in turn.candidates] == ["Un article de ce matin"]
    # The set goes on: restricted without a subject.
    more = api.ask(context, conversation.id, "Sans autre chose")
    answer(worker, context, conversation.id, more.id)
    found = api.get(context, conversation.id)
    assert found is not None and found.turns[1].operation is Operation.EXCLURE
