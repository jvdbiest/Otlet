# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the Reporter (A2-1, ADR-0044), under a workspace: conversations whose answers are
sets of items and lines of fact cited by source. The API records a question; the worker
answers it (DR6), and the interface reads the conversation again until the turn is done."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from otlet.assistant.domain.terms import Concept, TermsError
from otlet.entrypoints.api.assistant import (
    CandidateView,
    ConceptBody,
    ConceptView,
    JudgedView,
)
from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.reporter.application.reporter import Conversation, Reporter, ReporterError, Turn
from otlet.workspaces.domain.model import WorkspaceContext


class QuestionBody(BaseModel):
    question: str = Field(max_length=1000)


class TermsBody(BaseModel):
    concepts: list[ConceptBody] = Field(min_length=1, max_length=4)


class FactLineView(BaseModel):
    item_id: UUID
    publisher: str
    figure: str
    measure: str
    when: str
    where: str
    passage: str
    figure_in_passage: bool


class ComparedView(BaseModel):
    first: int  # positions in lines
    second: int
    same: bool


class FactView(BaseModel):
    lines: list[FactLineView]
    agreement: Literal["concordent", "divergent", "partiel", "une source", "absent"]
    compared: list[ComparedView]
    conclusion: str
    dropped: int  # lines of the model whose passage is not in the article
    read: list[UUID]  # the items read to answer


class TurnCandidateView(CandidateView):
    judged: JudgedView | None  # after a sort only


class TurnView(BaseModel):
    id: UUID
    position: int
    question: str
    status: Literal["pending", "done", "failed"]
    operation: Literal["chercher", "restreindre", "élargir", "trier", "fait", "agir"] | None
    language: str | None
    concepts: list[ConceptView]
    candidates: list[TurnCandidateView]
    fact: FactView | None
    error: str | None
    model: str | None
    created_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def of(cls, turn: Turn) -> "TurnView":
        fact = turn.fact
        return cls(
            id=turn.id,
            position=turn.position,
            question=turn.question,
            status=turn.status,
            operation=None if turn.operation is None else turn.operation.value,
            language=turn.state.language,
            concepts=[
                ConceptView(
                    name=w.concept.name,
                    terms=list(w.concept.terms),
                    added=list(w.added),
                    counts={t: turn.term_counts[t] for t in w.all_terms if t in turn.term_counts},
                    general=list(w.general),
                )
                for w in turn.concepts
            ],
            candidates=[
                TurnCandidateView(
                    **CandidateView.of(c).model_dump(),
                    judged=None
                    if (j := turn.verdicts.get(c.id)) is None
                    else JudgedView(verdict=j.verdict.value, reason=j.reason, by_model=j.by_model),
                )
                for c in turn.candidates
            ],
            fact=None
            if fact is None
            else FactView(
                lines=[
                    FactLineView(
                        item_id=UUID(f.item_id),
                        publisher=f.publisher,
                        figure=f.figure,
                        measure=f.measure,
                        when=f.when,
                        where=f.where,
                        passage=f.passage,
                        figure_in_passage=f.figure_in_passage,
                    )
                    for f in fact.lines
                ],
                agreement=fact.agreement.value,
                compared=[
                    ComparedView(first=c.first, second=c.second, same=c.same) for c in fact.compared
                ],
                conclusion=fact.conclusion,
                dropped=fact.dropped,
                read=[UUID(i) for i in fact.read],
            ),
            error=turn.error,
            model=turn.model,
            created_at=turn.created_at,
            finished_at=turn.finished_at,
        )


class ConversationView(BaseModel):
    id: UUID
    title: str
    days: int | None
    created_at: datetime | None
    turns: list[TurnView]

    @classmethod
    def of(cls, conversation: Conversation) -> "ConversationView":
        return cls(
            id=conversation.id,
            title=conversation.title,
            days=conversation.days,
            created_at=conversation.created_at,
            turns=[TurnView.of(t) for t in conversation.turns],
        )


class ConversationSummaryView(BaseModel):
    id: UUID
    title: str
    created_at: datetime | None


def _refused(error: TermsError | ReporterError) -> HTTPException:
    if isinstance(error, ReporterError) and error.code == "not_found":
        return HTTPException(status.HTTP_404_NOT_FOUND, "conversation_not_found")
    if isinstance(error, ReporterError) and error.code == "turn_pending":
        return HTTPException(status.HTTP_409_CONFLICT, error.code)
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.code)


def build_router(
    reporter: Reporter, workspace_context: Callable[..., WorkspaceContext]
) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(
        prefix=PREFIX + "/{workspace_id}/reporter", dependencies=[Depends(same_origin)]
    )

    @router.post("/conversations", status_code=status.HTTP_202_ACCEPTED)
    def start(body: QuestionBody, context: Context) -> ConversationView:
        """Starts a conversation with its first question; the worker answers it."""
        try:
            return ConversationView.of(reporter.start(context, body.question))
        except ReporterError as error:
            raise _refused(error) from error

    @router.get("/conversations")
    def recent(context: Context) -> list[ConversationSummaryView]:
        """The recent conversations of the user, the newest first."""
        return [
            ConversationSummaryView(id=c.id, title=c.title, created_at=c.created_at)
            for c in reporter.recent(context)
        ]

    @router.get("/conversations/{conversation_id}")
    def get(conversation_id: UUID, context: Context) -> ConversationView:
        conversation = reporter.get(context, conversation_id)
        if conversation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation_not_found")
        return ConversationView.of(conversation)

    @router.post("/conversations/{conversation_id}/turns", status_code=status.HTTP_202_ACCEPTED)
    def ask(conversation_id: UUID, body: QuestionBody, context: Context) -> TurnView:
        """A new question; refused while the previous one is being answered."""
        try:
            return TurnView.of(reporter.ask(context, conversation_id, body.question))
        except ReporterError as error:
            raise _refused(error) from error

    @router.put("/conversations/{conversation_id}/turns/{turn_id}/terms")
    def set_terms(
        conversation_id: UUID, turn_id: UUID, body: TermsBody, context: Context
    ) -> TurnView:
        """The author's terms for the last set: found again at once, without a model."""
        concepts = [Concept(c.name, tuple(c.terms)) for c in body.concepts]
        try:
            return TurnView.of(reporter.set_terms(context, conversation_id, turn_id, concepts))
        except (ReporterError, TermsError) as error:
            raise _refused(error) from error

    return router
