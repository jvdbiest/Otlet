# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the Assistant de veille (A1b-1, ADR-0043), under a workspace: the glossary of the
workspace, and the matter of a subject found by its concepts, without a model."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from otlet.assistant.application.assistant import Assistant, Candidate, StoredEntry
from otlet.assistant.application.dossiers import Dossier, DossierError, Dossiers
from otlet.assistant.domain.qualify import Judged
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
    counts: dict[str, int] = {}  # the items each term finds alone, in the period
    general: list[str] = []  # set aside as too general: shown, not searched


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


class JudgedView(BaseModel):
    verdict: Literal["traite", "proche", "hors_sujet"]
    reason: str
    by_model: bool  # False: set by a rule (no summary, not judged)


class DossierCandidateView(CandidateView):
    judged: JudgedView | None  # None while the model judges


class DossierBody(BaseModel):
    subject: str = Field(max_length=400)
    angle: str = Field(default="", max_length=1000)
    days: int | None = Field(default=30, ge=1, le=3650)
    concepts: list[ConceptBody] = Field(default=[], max_length=4)  # none: the model proposes


class DossierView(BaseModel):
    id: UUID
    subject: str
    angle: str
    days: int | None
    status: Literal["pending", "qualifying", "done"]
    concepts: list[ConceptView]
    candidates: list[DossierCandidateView]
    error: str | None
    model: str | None
    created_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def of(cls, dossier: Dossier) -> "DossierView":
        def judged(found: Judged | None) -> JudgedView | None:
            if found is None:
                return None
            return JudgedView(
                verdict=found.verdict.value, reason=found.reason, by_model=found.by_model
            )

        return cls(
            id=dossier.id,
            subject=dossier.subject,
            angle=dossier.angle,
            days=dossier.days,
            status=dossier.status,
            concepts=[
                ConceptView(
                    name=w.concept.name,
                    terms=list(w.concept.terms),
                    added=list(w.added),
                    counts={
                        t: dossier.term_counts[t] for t in w.all_terms if t in dossier.term_counts
                    },
                    general=list(w.general),
                )
                for w in dossier.concepts
            ],
            candidates=[
                DossierCandidateView(
                    **CandidateView.of(c).model_dump(), judged=judged(dossier.verdicts.get(c.id))
                )
                for c in dossier.candidates
            ],
            error=dossier.error,
            model=dossier.model,
            created_at=dossier.created_at,
            finished_at=dossier.finished_at,
        )


class DossierSummaryView(BaseModel):
    id: UUID
    subject: str
    status: Literal["pending", "qualifying", "done"]
    candidates: int
    created_at: datetime | None


def _refused(error: TermsError | DossierError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.code)


def build_router(
    assistant: Assistant,
    dossiers: Dossiers,
    workspace_context: Callable[..., WorkspaceContext],
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

    @router.post("/assistant/dossiers", status_code=status.HTTP_202_ACCEPTED)
    def start_dossier(body: DossierBody, context: Context) -> DossierView:
        """Starts a dossier: the worker finds the candidates, without a model, then the model
        of the author judges them. Read it again until its status is « done »."""
        concepts = [Concept(c.name, tuple(c.terms)) for c in body.concepts]
        try:
            dossier = dossiers.start(context, body.subject, body.angle, body.days, concepts)
        except (TermsError, DossierError) as error:
            raise _refused(error) from error
        return DossierView.of(dossier)

    @router.get("/assistant/dossiers")
    def list_dossiers(context: Context) -> list[DossierSummaryView]:
        """The recent dossiers of the user, the newest first."""
        return [
            DossierSummaryView(
                id=d.id,
                subject=d.subject,
                status=d.status,
                candidates=len(d.candidates),
                created_at=d.created_at,
            )
            for d in dossiers.recent(context)
        ]

    @router.post("/assistant/dossiers/{dossier_id}/cancel")
    def cancel_dossier(dossier_id: UUID, context: Context) -> DossierView:
        dossier = dossiers.cancel(context, dossier_id)
        if dossier is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "dossier_not_found")
        return DossierView.of(dossier)

    @router.get("/assistant/dossiers/{dossier_id}")
    def get_dossier(dossier_id: UUID, context: Context) -> DossierView:
        dossier = dossiers.get(context, dossier_id)
        if dossier is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "dossier_not_found")
        return DossierView.of(dossier)

    return router
