# SPDX-License-Identifier: AGPL-3.0-or-later
"""The dossiers of the Assistant de veille (A1b-1, ADR-0043): a subject, its concepts widened by
the glossary, the items found without a model, then ordered by the model of the author.

A dossier is started by the API and run by the worker, the only process that opens the keys of
providers (DR6): the model proposes the concepts when the author gave none, then judges the
candidates by batches. Whatever the model does, no item leaves the dossier: an item it could
not judge goes « à vérifier », and a dossier whose model failed still shows every candidate.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from otlet.assistant.application.assistant import CANDIDATES_MAX, AssistantStore, Candidate
from otlet.assistant.domain.qualify import (
    BATCH,
    EXPAND_SCHEMA,
    EXPAND_SYSTEM,
    NO_SUMMARY,
    NOT_JUDGED,
    PROMPT_VERSION,
    QUALIFY_SCHEMA,
    QUALIFY_SYSTEM,
    Judged,
    Line,
    check_expand,
    check_qualify,
    qualify_message,
    read_expand,
    read_qualify,
    subject_message,
)
from otlet.assistant.domain.terms import (
    Concept,
    TermsError,
    Widened,
    checked_concepts,
    publisher_country,
    widen,
)
from otlet.workspaces.domain.model import WorkspaceContext

QUALIFY_DOSSIER = "assistant.qualify_dossier"
SUBJECT_MAX_LENGTH = 200
# Room for the answer: a « thinking » local model (qwen3) spends its output on reasoning
# first; with 600 tokens it was cut before the concepts (Joël, 2026-10-25). A local model
# costs nothing per token (drafts.py, LOCAL_OUTPUT_TOKENS).
EXPAND_OUTPUT_TOKENS = 4096
QUALIFY_OUTPUT_TOKENS = 8192
ANGLE_MAX_LENGTH = 500


class DossierError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Dossier:
    id: UUID
    subject: str
    angle: str
    days: int | None
    status: str  # pending, searching, qualifying, done
    concepts: list[Widened] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    verdicts: dict[UUID, Judged] = field(default_factory=dict)
    error: str | None = None
    model: str | None = None
    prompt_version: str = PROMPT_VERSION
    attempts: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None
    finished_at: datetime | None = None
    # The items each term finds alone (folded term → count), in the period: a term that
    # finds nothing, or a concept no item shares with another, is seen at once.
    term_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Asked:
    """An answer of the model, or why there is none."""

    text: str | None
    error: str | None
    model: str | None
    attempts: tuple[dict[str, Any], ...]


class Model(Protocol):
    """The AI gateway, as the assistant sees it: the profile of the author."""

    def ask(
        self,
        user_id: UUID,
        system: str,
        user: str,
        schema: dict[str, Any],
        validate: Callable[[str], list[str]],
        max_output_tokens: int,
    ) -> Asked: ...


class DossierStore(Protocol):
    def start_dossier(
        self,
        workspace_id: UUID,
        user_id: UUID,
        subject: str,
        angle: str,
        days: int | None,
        concepts: list[Concept],
    ) -> Dossier:
        """Records the dossier, pending, and enqueues QUALIFY_DOSSIER, in one transaction."""
        ...

    def dossier(self, workspace_id: UUID, dossier_id: UUID) -> Dossier | None: ...

    def dossiers(self, workspace_id: UUID, user_id: UUID, limit: int) -> list[Dossier]: ...

    def requested_concepts(self, workspace_id: UUID, dossier_id: UUID) -> list[Concept]: ...

    def save_dossier(self, workspace_id: UUID, dossier: Dossier, finished: bool) -> None: ...


class Dossiers:
    def __init__(
        self,
        store: DossierStore,
        search: AssistantStore,
        model: Model | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._search = search
        self._model = model
        self._now = now

    def start(
        self,
        context: WorkspaceContext,
        subject: str,
        angle: str = "",
        days: int | None = 30,
        concepts: list[Concept] | None = None,
    ) -> Dossier:
        """A dossier for the subject; the worker fills it. `concepts`: the author's terms (the
        model proposes them when there are none)."""
        subject = " ".join(subject.split())
        angle = " ".join(angle.split())
        if not 1 <= len(subject) <= SUBJECT_MAX_LENGTH:
            raise DossierError(
                "invalid_subject", f"a subject has 1 to {SUBJECT_MAX_LENGTH} characters"
            )
        if len(angle) > ANGLE_MAX_LENGTH:
            raise DossierError(
                "invalid_angle", f"an angle has at most {ANGLE_MAX_LENGTH} characters"
            )
        checked = checked_concepts(concepts) if concepts else []
        return self._store.start_dossier(
            context.workspace_id, context.user_id, subject, angle, days, checked
        )

    def get(self, context: WorkspaceContext, dossier_id: UUID) -> Dossier | None:
        return self._store.dossier(context.workspace_id, dossier_id)

    def recent(self, context: WorkspaceContext, limit: int = 20) -> list[Dossier]:
        return self._store.dossiers(context.workspace_id, context.user_id, limit)

    def run(self, workspace_id: UUID, user_id: UUID, dossier_id: UUID) -> None:
        """The work of the worker: concepts, candidates, verdicts; saved at each stage, so the
        interface shows the candidates while the model still judges them."""
        if self._model is None:
            raise RuntimeError("the model is only reached from the worker")
        dossier = self._store.dossier(workspace_id, dossier_id)
        if dossier is None or dossier.status == "done":
            return
        attempts: list[dict[str, Any]] = []
        models: list[str] = []
        errors: list[str] = []
        concepts = self._store.requested_concepts(workspace_id, dossier_id)
        if not concepts:
            concepts = self._expand(user_id, dossier, attempts, models, errors)
        glossary = [stored.entry for stored in self._search.glossary(workspace_id)]
        widened = widen(concepts, glossary)
        since = None if dossier.days is None else self._now() - timedelta(days=dossier.days)
        candidates = self._search.candidates(workspace_id, widened, since, CANDIDATES_MAX)
        counts = self._search.term_counts(
            workspace_id, [term for w in widened for term in w.terms], since
        )
        dossier = Dossier(
            id=dossier.id,
            subject=dossier.subject,
            angle=dossier.angle,
            days=dossier.days,
            status="qualifying",
            concepts=widened,
            candidates=candidates,
            created_at=dossier.created_at,
            term_counts=counts,
        )
        self._store.save_dossier(workspace_id, dossier, finished=False)
        verdicts = self._qualify(user_id, dossier, attempts, models, errors)
        self._store.save_dossier(
            workspace_id,
            Dossier(
                id=dossier.id,
                subject=dossier.subject,
                angle=dossier.angle,
                days=dossier.days,
                status="done",
                concepts=widened,
                candidates=candidates,
                verdicts=verdicts,
                error="; ".join(dict.fromkeys(errors)) or None,
                model=", ".join(dict.fromkeys(models)) or None,
                attempts=attempts,
                created_at=dossier.created_at,
                term_counts=counts,
            ),
            finished=True,
        )

    def _ask(
        self,
        user_id: UUID,
        system: str,
        user: str,
        schema: dict[str, Any],
        validate: Callable[[str], list[str]],
        max_output_tokens: int,
        attempts: list[dict[str, Any]],
        models: list[str],
        errors: list[str],
    ) -> str | None:
        if self._model is None:
            raise RuntimeError("the model is only reached from the worker")
        asked = self._model.ask(user_id, system, user, schema, validate, max_output_tokens)
        attempts.extend(asked.attempts)
        if asked.model:
            models.append(asked.model)
        if asked.text is None:
            errors.append(asked.error or "no answer")
        return asked.text

    def _expand(
        self,
        user_id: UUID,
        dossier: Dossier,
        attempts: list[dict[str, Any]],
        models: list[str],
        errors: list[str],
    ) -> list[Concept]:
        """The concepts the model proposes; the subject itself as one term when it fails."""
        raw = self._ask(
            user_id,
            EXPAND_SYSTEM,
            # The subject alone: the angle orients the sort, it never narrows the search
            # (a concept « Belgique » set aside every item that does not write it).
            subject_message(dossier.subject, ""),
            EXPAND_SCHEMA,
            check_expand,
            EXPAND_OUTPUT_TOKENS,
            attempts,
            models,
            errors,
        )
        if raw is not None:
            try:
                return checked_concepts(
                    [Concept(name, tuple(terms)) for name, terms in read_expand(raw)]
                )
            except TermsError as error:
                errors.append(str(error))
        return [Concept(dossier.subject, (dossier.subject,))]

    def _qualify(
        self,
        user_id: UUID,
        dossier: Dossier,
        attempts: list[dict[str, Any]],
        models: list[str],
        errors: list[str],
    ) -> dict[UUID, Judged]:
        verdicts: dict[UUID, Judged] = {}
        sent: list[Candidate] = []
        for candidate in dossier.candidates:
            if candidate.summary.strip():
                sent.append(candidate)
            else:
                verdicts[candidate.id] = NO_SUMMARY
        for start in range(0, len(sent), BATCH):
            batch = sent[start : start + BATCH]
            lines = [
                Line(c.title, c.summary, c.language, c.publisher, publisher_country(c.url))
                for c in batch
            ]
            raw = self._ask(
                user_id,
                QUALIFY_SYSTEM,
                qualify_message(dossier.subject, dossier.angle, lines),
                QUALIFY_SCHEMA,
                check_qualify,
                QUALIFY_OUTPUT_TOKENS,
                attempts,
                models,
                errors,
            )
            judged = read_qualify(raw, len(batch)) if raw is not None else {}
            for n, candidate in enumerate(batch, 1):
                verdicts[candidate.id] = judged.get(n, NOT_JUDGED)
        return verdicts
