# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the Assistant de veille (A1b-1, ADR-0043), under a workspace: the glossary of the
workspace, and the matter of a subject found by its concepts, without a model."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from otlet.assistant.application.assistant import Assistant, Candidate, StoredEntry
from otlet.assistant.domain.terms import Concept, TermsError, publisher_country
from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.workspaces.domain.model import WorkspaceContext


class EntryView(BaseModel):
    id: UUID
    terms: list[str]
    updated_at: datetime

    @classmethod
    def of(cls, stored: StoredEntry) -> "EntryView":
        return cls(id=stored.id, terms=list(stored.entry.terms), updated_at=stored.updated_at)


class EntryBody(BaseModel):
    terms: list[str] = Field(max_length=60)


class ConceptBody(BaseModel):
    name: str = Field(max_length=200)
    terms: list[str] = Field(max_length=40)


class FindBody(BaseModel):
    concepts: list[ConceptBody] = Field(min_length=1, max_length=4)
    days: int | None = Field(default=30, ge=1, le=3650)  # None: every date


class ConceptView(BaseModel):
    name: str
    terms: list[str]  # those of the author
    added: list[str]  # those the glossary adds


class CandidateView(BaseModel):
    id: UUID
    title: str
    summary: str
    url: str | None
    language: str | None
    publisher: str | None
    country: str | None  # of the publisher, from the address of the item
    dated: datetime

    @classmethod
    def of(cls, candidate: Candidate) -> "CandidateView":
        return cls(
            id=candidate.id,
            title=candidate.title,
            summary=candidate.summary,
            url=candidate.url,
            language=candidate.language,
            publisher=candidate.publisher,
            country=publisher_country(candidate.url),
            dated=candidate.dated,
        )


class FoundView(BaseModel):
    concepts: list[ConceptView]
    candidates: list[CandidateView]


def _refused(error: TermsError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.code)


def build_router(
    assistant: Assistant, workspace_context: Callable[..., WorkspaceContext]
) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(prefix=PREFIX + "/{workspace_id}", dependencies=[Depends(same_origin)])

    @router.get("/glossary")
    def list_glossary(context: Context) -> list[EntryView]:
        """The entries of the glossary of the workspace, by their first term."""
        return [EntryView.of(stored) for stored in assistant.glossary(context)]

    @router.post("/glossary", status_code=status.HTTP_201_CREATED)
    def add_entry(body: EntryBody, context: Context) -> EntryView:
        """Adds terms that mean the same thing (2 to 30)."""
        try:
            return EntryView.of(assistant.add_entry(context, body.terms))
        except TermsError as error:
            raise _refused(error) from error

    @router.put("/glossary/{entry_id}")
    def update_entry(entry_id: UUID, body: EntryBody, context: Context) -> EntryView:
        try:
            stored = assistant.update_entry(context, entry_id, body.terms)
        except TermsError as error:
            raise _refused(error) from error
        if stored is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "entry_not_found")
        return EntryView.of(stored)

    @router.delete("/glossary/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_entry(entry_id: UUID, context: Context) -> None:
        if not assistant.delete_entry(context, entry_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "entry_not_found")

    @router.post("/assistant/find")
    def find(body: FindBody, context: Context) -> FoundView:
        """The items of the Veille holding a term of every concept, the concepts widened by the
        glossary. No model is called: what is searched is what is shown."""
        since = None if body.days is None else datetime.now(UTC) - timedelta(days=body.days)
        concepts = [Concept(c.name, tuple(c.terms)) for c in body.concepts]
        try:
            found = assistant.find(context, concepts, since)
        except TermsError as error:
            raise _refused(error) from error
        return FoundView(
            concepts=[
                ConceptView(name=w.concept.name, terms=list(w.concept.terms), added=list(w.added))
                for w in found.concepts
            ],
            candidates=[CandidateView.of(c) for c in found.candidates],
        )

    return router
