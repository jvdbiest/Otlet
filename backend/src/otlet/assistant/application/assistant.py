# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Assistant de veille (A1b-1, ADR-0043): the glossary of the workspace, and the matter of a
subject found by its concepts, widened by the glossary, without a model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from otlet.assistant.domain.terms import (
    Concept,
    GlossaryEntry,
    Widened,
    checked_concepts,
    checked_entry,
    widen,
)
from otlet.workspaces.domain.model import WorkspaceContext

CANDIDATES_MAX = 120


@dataclass(frozen=True, slots=True)
class StoredEntry:
    id: UUID
    entry: GlossaryEntry
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Candidate:
    """An item found for the subject, as the dossier shows it and the model reads it."""

    id: UUID
    title: str
    summary: str
    url: str | None
    language: str | None
    publisher: str | None
    dated: datetime


@dataclass(frozen=True, slots=True)
class Found:
    concepts: list[Widened]
    candidates: list[Candidate]


class AssistantStore(Protocol):
    def glossary(self, workspace_id: UUID) -> list[StoredEntry]: ...

    def add_entry(
        self, workspace_id: UUID, user_id: UUID, terms: tuple[str, ...]
    ) -> StoredEntry: ...

    def update_entry(
        self, workspace_id: UUID, entry_id: UUID, terms: tuple[str, ...]
    ) -> StoredEntry | None: ...

    def delete_entry(self, workspace_id: UUID, entry_id: UUID) -> bool: ...

    def candidates(
        self, workspace_id: UUID, concepts: list[Widened], since: datetime | None, limit: int
    ) -> list[Candidate]: ...


class Assistant:
    def __init__(self, store: AssistantStore) -> None:
        self._store = store

    def glossary(self, context: WorkspaceContext) -> list[StoredEntry]:
        return self._store.glossary(context.workspace_id)

    def add_entry(self, context: WorkspaceContext, terms: list[str]) -> StoredEntry:
        return self._store.add_entry(context.workspace_id, context.user_id, checked_entry(terms))

    def update_entry(
        self, context: WorkspaceContext, entry_id: UUID, terms: list[str]
    ) -> StoredEntry | None:
        return self._store.update_entry(context.workspace_id, entry_id, checked_entry(terms))

    def delete_entry(self, context: WorkspaceContext, entry_id: UUID) -> bool:
        return self._store.delete_entry(context.workspace_id, entry_id)

    def find(
        self, context: WorkspaceContext, concepts: list[Concept], since: datetime | None = None
    ) -> Found:
        """The concepts widened by the glossary, and the items holding a term of each."""
        glossary = [stored.entry for stored in self._store.glossary(context.workspace_id)]
        widened = widen(checked_concepts(concepts), glossary)
        candidates = self._store.candidates(context.workspace_id, widened, since, CANDIDATES_MAX)
        return Found(widened, candidates)
