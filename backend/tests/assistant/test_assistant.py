# SPDX-License-Identifier: AGPL-3.0-or-later
"""The glossary and the search by concepts on a real PostgreSQL (ADR-0043)."""

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.assistant.application.assistant import Assistant
from otlet.assistant.domain.terms import Concept, TermsError
from otlet.collection.adapters.postgres import PostgresCollectionStore
from otlet.collection.application.ports import NewItem, Outcome
from otlet.collection.domain.model import FeedEntry, TextStatus
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces
from otlet.workspaces.domain.model import WorkspaceContext

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


@pytest.fixture
def assistant(migrated: TestDatabase) -> tuple[Assistant, WorkspaceContext, sa.Engine]:
    engine = db.create_engine(migrated.app_url)
    context = context_for(engine, "alice@example.org")
    collect(
        engine,
        context,
        "ladh",
        "fr",
        [
            (
                "Le budget de la Région bruxelloise sous pression",
                "Le gouvernement bruxellois cherche des économies.",
                1,
            ),
            (
                "Budget fédéral : l'Horeca inquiet",
                "La TVA pourrait augmenter au niveau fédéral.",
                2,
            ),
            ("Ancien budget de Bruxelles", "Le budget bruxellois de l'an dernier.", 60),
        ],
    )
    collect(
        engine,
        context,
        "bruzz",
        "nl",
        [
            (
                "Brusselse begroting: besparingen op bibliotheken",
                "Het Brussels Gewest bespaart.",
                1,
            ),
        ],
    )
    return Assistant(PostgresAssistantStore(engine)), context, engine


def test_the_glossary_finds_the_other_language(
    assistant: tuple[Assistant, WorkspaceContext, sa.Engine],
) -> None:
    service, context, engine = assistant
    concepts = [Concept("budget", ("budget",)), Concept("Bruxelles", ("bruxellois", "bruxelloise"))]
    week = NOW - timedelta(days=7)
    alone = service.find(context, concepts, since=week)
    assert [c.title for c in alone.candidates] == [
        "Le budget de la Région bruxelloise sous pression"
    ]
    service.add_entry(context, ["budget", "begroting"])
    service.add_entry(context, ["bruxellois", "Brusselse", "Brussel"])
    widened = service.find(context, concepts, since=week)
    assert widened.concepts[0].added == ("begroting",)
    assert {c.title for c in widened.candidates} == {
        "Le budget de la Région bruxelloise sous pression",
        "Brusselse begroting: besparingen op bibliotheken",
    }
    dutch = next(c for c in widened.candidates if c.language and c.language.startswith("nl"))
    assert (dutch.publisher, dutch.url) == ("bruzz", "https://bruzz.example.be/0")
    # Without a period, the older item too; the federal budget never (no term of Bruxelles).
    every = service.find(context, concepts)
    assert len(every.candidates) == 3
    # A term of several words holds when the item has all of them, not as an exact phrase.
    loose = service.find(
        context, [Concept("budget", ("budget",)), Concept("Bruxelles", ("bruxelloise région",))]
    )
    assert [c.title for c in loose.candidates] == [
        "Le budget de la Région bruxelloise sous pression"
    ]
    # The glossary of another workspace is not this one's.
    other = context_for(engine, "bob@example.org")
    assert service.glossary(other) == []


def test_the_glossary_is_kept_and_edited(
    assistant: tuple[Assistant, WorkspaceContext, sa.Engine],
) -> None:
    service, context, _ = assistant
    entry = service.add_entry(context, [" Bruxelles-Capitale ", "Brussels Hoofdstedelijk Gewest"])
    assert entry.entry.terms == ("Bruxelles-Capitale", "Brussels Hoofdstedelijk Gewest")
    changed = service.update_entry(
        context, entry.id, ["Bruxelles-Capitale", "Brussels-Capital Region"]
    )
    assert changed is not None and changed.entry.terms[1] == "Brussels-Capital Region"
    with pytest.raises(TermsError):
        service.add_entry(context, ["seul"])
    assert service.delete_entry(context, entry.id) is True
    assert service.glossary(context) == []


class FakeModel:
    """Proposes the concepts of the budget, then judges by a word of the title."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.asked: list[str] = []

    def ask(self, user_id, system, user, schema, validate, max_output_tokens):  # type: ignore[no-untyped-def]
        import json

        from otlet.assistant.application.dossiers import Asked

        self.asked.append(user)
        if self.fail:
            return Asked(None, "no model", None, ({"result": "error"},))
        if "Éléments :" not in user:
            concepts = [
                {"name": "budget", "terms": ["budget"]},
                {"name": "Bruxelles", "terms": ["bruxelloise"]},
            ]
            return Asked(json.dumps({"concepts": concepts}), None, "fake", ())
        lines = [line for line in user.splitlines() if line[:1].isdigit()]
        verdicts = [
            {"n": n, "verdict": "traite" if "Région" in line else "hors_sujet", "raison": "r"}
            for n, line in enumerate(lines, 1)
        ] + [{"n": 99, "verdict": "traite", "raison": "inventé"}]
        return Asked(json.dumps({"verdicts": verdicts}), None, "fake", ())


def test_a_dossier_finds_without_a_model_then_orders(
    assistant: tuple[Assistant, WorkspaceContext, sa.Engine],
) -> None:
    from otlet.assistant.application.dossiers import Dossiers
    from otlet.assistant.domain.qualify import Verdict

    service, context, engine = assistant
    service.add_entry(context, ["bruxelloise", "Brusselse"])
    service.add_entry(context, ["budget", "begroting"])
    enqueued: list[str] = []

    def enqueue(connection: sa.Connection, name: str, **kwargs: object) -> int:
        enqueued.append(name)
        return 1

    store = PostgresAssistantStore(engine, enqueue)
    model = FakeModel()
    dossiers = Dossiers(store, store, model)
    started = dossiers.start(context, "  Budget de la Région de Bruxelles-Capitale ", days=7)
    assert (started.status, started.subject, enqueued) == (
        "pending",
        "Budget de la Région de Bruxelles-Capitale",
        ["assistant.qualify_dossier"],
    )
    dossiers.run(context.workspace_id, context.user_id, started.id)
    done = dossiers.get(context, started.id)
    assert done is not None and done.status == "done" and done.model == "fake"
    # The model's concepts, widened by the glossary: the Dutch item is found.
    assert done.concepts[1].added == ("Brusselse",)
    # Each term counts the items it finds alone: a term that finds nothing shows at once.
    assert done.term_counts["Brusselse"] == 1 and done.term_counts["budget"] == 2
    by_title = {c.title: done.verdicts[c.id].verdict for c in done.candidates}
    assert by_title == {
        "Le budget de la Région bruxelloise sous pression": Verdict.TRAITE,
        "Brusselse begroting: besparingen op bibliotheken": Verdict.HORS_SUJET,
    }
    assert "pays inconnu" not in model.asked[-1] and "Belgique" in model.asked[-1]
    assert [d.id for d in dossiers.recent(context)] == [started.id]


def test_a_dossier_whose_model_fails_still_shows_every_candidate(
    assistant: tuple[Assistant, WorkspaceContext, sa.Engine],
) -> None:
    from otlet.assistant.application.dossiers import Dossiers
    from otlet.assistant.domain.qualify import NOT_JUDGED

    service, context, engine = assistant
    store = PostgresAssistantStore(engine, lambda connection, name, **kwargs: 1)
    dossiers = Dossiers(store, store, FakeModel(fail=True))
    started = dossiers.start(
        context, "Budget", days=None, concepts=[Concept("budget", ("budget",))]
    )
    dossiers.run(context.workspace_id, context.user_id, started.id)
    done = dossiers.get(context, started.id)
    assert done is not None and done.error == "no model" and len(done.candidates) == 3
    assert all(done.verdicts[c.id] == NOT_JUDGED for c in done.candidates)
