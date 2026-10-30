# SPDX-License-Identifier: AGPL-3.0-or-later
"""The meaning of the items (ADR-0045, sens-1), with a fake encoder; the real model is measured
in spikes/a2-sens."""

import uuid
from collections.abc import Sequence
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
from otlet.meaning.adapters.postgres import PostgresMeaningStore
from otlet.meaning.application.meaning import Meaning, MeaningStore, Pending
from otlet.meaning.domain.meaning import DIMENSIONS, MODEL, text_of
from otlet.platform import database as db
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces
from otlet.workspaces.domain.model import WorkspaceContext

NOW = datetime.now(UTC)
NOW_ID = uuid.uuid4()


class FakeEncoder:
    """A vector from the length of the text: enough to tell the items apart."""

    def __init__(self) -> None:
        self.texts: list[str] = []

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.texts.extend(texts)
        return [[float(len(t) % 7 + 1)] + [0.0] * (DIMENSIONS - 1) for t in texts]


def test_the_text_encoded_is_the_title_and_the_start_of_the_summary() -> None:
    assert text_of(" Tempête  Austen ", "Quatre blessés.\n" + "x" * 500) == (
        "Tempête Austen. Quatre blessés. " + "x" * 284
    )
    assert text_of("Tempête Austen", "  ") == "Tempête Austen"


class MemoryStore(MeaningStore):
    def __init__(self, count: int) -> None:
        self.left = [Pending(NOW_ID, NOW_ID, f"titre {n}", "") for n in range(count)]
        self.saved: list[tuple[Pending, list[float]]] = []

    def pending(self, limit: int) -> list[Pending]:
        return self.left[:limit]

    def save(self, vectors: list[tuple[Pending, list[float]]], model: str) -> None:
        assert model == MODEL
        self.saved.extend(vectors)
        self.left = self.left[len(vectors) :]


def test_the_model_is_loaded_only_when_there_is_work_and_the_budget_stops_it() -> None:
    built: list[FakeEncoder] = []

    def encoder() -> FakeEncoder:
        built.append(FakeEncoder())
        return built[-1]

    assert Meaning(MemoryStore(0), encoder).encode_pending() == 0
    assert built == []
    ticks = iter([0.0, 1.0, 2.0, 500.0])
    store = MemoryStore(100)
    assert Meaning(store, encoder, clock=lambda: next(ticks)).encode_pending(budget=10) == 64
    assert len(built) == 1 and len(store.saved) == 64


def test_a_vector_of_the_wrong_size_is_refused() -> None:
    class Short:
        def encode(self, texts: Sequence[str]) -> list[list[float]]:
            return [[1.0] for _ in texts]

    with pytest.raises(ValueError):
        Meaning(MemoryStore(1), Short).encode_pending()


def context_for(engine: sa.Engine, login: str) -> WorkspaceContext:
    user = Authentication(PostgresIdentityStore(engine), Argon2Hasher()).create_user(
        login, login, "une phrase de passe assez longue"
    )
    workspaces = Workspaces(PostgresWorkspaceStore(engine))
    context = workspaces.enter(user, workspaces.create(user, "Veille").id)
    assert context is not None
    return context


def collect(engine: sa.Engine, context: WorkspaceContext, titles: list[str]) -> None:
    store = PostgresCollectionStore(engine, lambda connection, name, **kwargs: 0)
    source_id = store.add_source(
        context.workspace_id,
        name="journal",
        url="https://journal.example.be/feed",
        feed_url="https://journal.example.be/feed",
        site_url=None,
        interval_minutes=60,
    ).id
    entries = [
        NewItem(
            FeedEntry(
                guid=title,
                url=f"https://journal.example.be/{n}",
                title=title,
                author=None,
                published_at=NOW - timedelta(hours=n),
                summary=f"Résumé de {title}.",
                content=None,
                language="fr",
            ),
            TextStatus.SUMMARY_ONLY,
            "test",
        )
        for n, title in enumerate(titles)
    ]
    outcome = Outcome(fetched_at=NOW, next_fetch_at=NOW, success=True)
    store.finish_collection(context.workspace_id, source_id, outcome, entries)


def vectors(engine: sa.Engine, context: WorkspaceContext) -> list[tuple[str, str | None]]:
    with db.workspace_transaction(engine, context.workspace_id) as connection:
        rows = connection.execute(
            sa.text(
                "SELECT title, meaning_model FROM source_items"
                " WHERE meaning IS NOT NULL ORDER BY title"
            )
        ).all()
    return [(r.title, r.meaning_model) for r in rows]


@requires_database
def test_the_items_of_every_workspace_are_encoded_once(migrated: TestDatabase) -> None:
    engine = db.create_engine(migrated.app_url)
    alice = context_for(engine, "alice@example.org")
    bob = context_for(engine, "bob@example.org")
    collect(engine, alice, ["Vlaamse ziekenhuizen", "Hôpitaux en Flandre"])
    collect(engine, bob, ["Budget bruxellois"])
    encoder = FakeEncoder()
    meaning = Meaning(PostgresMeaningStore(engine), lambda: encoder)
    assert meaning.encode_pending() == 3
    assert vectors(engine, alice) == [
        ("Hôpitaux en Flandre", MODEL),
        ("Vlaamse ziekenhuizen", MODEL),
    ]
    assert vectors(engine, bob) == [("Budget bruxellois", MODEL)]
    assert "Budget bruxellois. Résumé de Budget bruxellois." in encoder.texts
    # Nothing left: the model is not even built.
    assert Meaning(PostgresMeaningStore(engine), lambda: FakeEncoder()).encode_pending() == 0
    # A workspace reads only its own items, vectors included.
    with db.workspace_transaction(engine, bob.workspace_id) as connection:
        count = connection.execute(
            sa.text("SELECT count(*) FROM source_items WHERE meaning IS NOT NULL")
        ).scalar_one()
    assert count == 1
