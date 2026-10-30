# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the Reporter (A2-1, ADR-0044), under a workspace: conversations whose answers are
sets of items and lines of fact cited by source. The API records a question; the worker
answers it (DR6), and the interface reads the conversation again until the turn is done."""

from collections.abc import Callable
from datetime import date, datetime
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
from otlet.reporter.application.reporter import (
    LIST_MAX,
    Conversation,
    Reporter,
    ReporterError,
    Turn,
)
from otlet.reporter.domain.questions import unsearched
from otlet.reporter.domain.themes import themes
from otlet.workspaces.domain.model import WorkspaceContext


class QuestionBody(BaseModel):
    question: str = Field(max_length=1000)
    # « Lire avant de répondre »: the set is read by the model before the answer is shown.
    read: bool = False
    # Dates chosen on the calendar, with the first question; both included.
    date_from: date | None = None
    date_to: date | None = None


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


class ReadConceptView(BaseModel):
    name: str
    terms: list[str]


class RoundView(BaseModel):
    concepts: list[ReadConceptView]
    read: int  # items read
    found: int  # items the search found


class AnswerView(BaseModel):
    item_id: UUID
    title: str
    publisher: str
    dated: str
    url: str | None
    reason: str
    round: int


class ReadingView(BaseModel):
    """« Vérifier en lisant »: what the model read, what truly answers, what is missing."""

    requested: bool
    rounds: list[RoundView]
    answers: list[AnswerView]
    coverage: Literal["oui", "partiel", "non"] | None
    missing: str
    errors: list[str]


class TurnCandidateView(CandidateView):
    judged: JudgedView | None  # after a sort only


class ThemeView(BaseModel):
    label: str
    items: list[UUID]


# A set this large is shown with its main themes (Joël, 2026-10-29).
THEMES_FROM = 25


class TurnView(BaseModel):
    id: UUID
    position: int
    question: str
    status: Literal["pending", "done", "failed"]
    operation: (
        Literal["chercher", "restreindre", "élargir", "trier", "fait", "agir", "exclure"] | None
    )
    excluded: list[str]
    date_from: date | None
    date_to: date | None
    language: str | None
    days: int | None  # a period the question named, in days
    concepts: list[ConceptView]
    candidates: list[TurnCandidateView]
    fact: FactView | None
    reading: ReadingView | None
    # Words of the question that no term searched (« enseignement »), and the main themes of
    # a large set: both without a model, to guide the author (Joël, 2026-10-29).
    unsearched: list[str]
    themes: list[ThemeView]
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
            excluded=list(turn.state.excluded),
            date_from=turn.state.date_from,
            date_to=turn.state.date_to,
            language=turn.state.language,
            days=turn.state.days,
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
            reading=None
            if (r := turn.reading) is None
            else ReadingView(
                requested=r.requested,
                rounds=[
                    RoundView(
                        concepts=[
                            ReadConceptView(name=c.name, terms=list(c.terms)) for c in rd.concepts
                        ],
                        read=len(rd.read),
                        found=rd.found,
                    )
                    for rd in r.rounds
                ],
                answers=[
                    AnswerView(
                        item_id=UUID(a.item_id),
                        title=a.title,
                        publisher=a.publisher,
                        dated=a.dated,
                        url=a.url,
                        reason=a.reason,
                        round=a.round,
                    )
                    for a in r.answers
                ],
                coverage=None if r.coverage is None else r.coverage.value,
                missing=r.missing,
                errors=list(r.errors),
            ),
            error=turn.error,
            model=turn.model,
            unsearched=unsearched(turn.question, [w.concept for w in turn.concepts])
            if turn.status == "done" and turn.concepts
            else [],
            themes=[
                ThemeView(label=t.label, items=[turn.candidates[n].id for n in t.members])
                for t in themes(
                    [f"{c.title} {c.summary}" for c in turn.candidates],
                    [term for w in turn.concepts for term in w.all_terms],
                )
            ]
            if len(turn.candidates) >= THEMES_FROM
            else [],
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


class DeleteBody(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=LIST_MAX)


class DeletedView(BaseModel):
    deleted: int


class ConversationSummaryView(BaseModel):
    id: UUID
    title: str
    created_at: datetime | None


def _refused(error: TermsError | ReporterError) -> HTTPException:
    if isinstance(error, ReporterError) and error.code == "not_found":
        return HTTPException(status.HTTP_404_NOT_FOUND, "conversation_not_found")
    if isinstance(error, ReporterError) and error.code in ("turn_pending", "already_read"):
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
            return ConversationView.of(
                reporter.start(context, body.question, body.read, (body.date_from, body.date_to))
            )
        except ReporterError as error:
            raise _refused(error) from error

    @router.get("/conversations")
    def recent(context: Context) -> list[ConversationSummaryView]:
        """The recent conversations of the user, the newest first."""
        return [
            ConversationSummaryView(id=c.id, title=c.title, created_at=c.created_at)
            for c in reporter.recent(context)
        ]

    @router.post("/conversations/delete")
    def delete(body: DeleteBody, context: Context) -> DeletedView:
        """Deletes the conversations chosen, for good."""
        return DeletedView(deleted=reporter.delete(context, body.ids))

    @router.get("/conversations/{conversation_id}")
    def get(conversation_id: UUID, context: Context) -> ConversationView:
        conversation = reporter.get(context, conversation_id)
        if conversation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation_not_found")
        return ConversationView.of(conversation)

    @router.post("/conversations/{conversation_id}/cancel")
    def cancel(conversation_id: UUID, context: Context) -> ConversationView:
        """Ends the question being answered; the worker cuts its call to the model."""
        conversation = reporter.cancel(context, conversation_id)
        if conversation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation_not_found")
        return ConversationView.of(conversation)

    @router.post("/conversations/{conversation_id}/turns", status_code=status.HTTP_202_ACCEPTED)
    def ask(conversation_id: UUID, body: QuestionBody, context: Context) -> TurnView:
        """A new question; refused while the previous one is being answered."""
        try:
            return TurnView.of(reporter.ask(context, conversation_id, body.question, body.read))
        except ReporterError as error:
            raise _refused(error) from error

    @router.post(
        "/conversations/{conversation_id}/turns/{turn_id}/more",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def read_more(conversation_id: UUID, turn_id: UUID, context: Context) -> TurnView:
        """A fact read further: the next items of the set; its lines are added."""
        try:
            return TurnView.of(reporter.read_more(context, conversation_id, turn_id))
        except ReporterError as error:
            raise _refused(error) from error

    @router.post(
        "/conversations/{conversation_id}/turns/{turn_id}/reading",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def read_set(conversation_id: UUID, turn_id: UUID, context: Context) -> TurnView:
        """« Vérifier en lisant »: the model reads the set of an answered question, once."""
        try:
            return TurnView.of(reporter.read_set(context, conversation_id, turn_id))
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
