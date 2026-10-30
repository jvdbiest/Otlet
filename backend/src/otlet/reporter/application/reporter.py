# SPDX-License-Identifier: AGPL-3.0-or-later
"""The conversations of the Reporter (A2-1, ADR-0044).

A question is recorded by the API and answered by the worker, the only process that opens the
keys of providers (DR6). The model translates the question into an operation; rules without a
model keep it to what the question says; the set follows from the concepts and the language,
found by the engine of the Assistant de veille (glossary, terms too general set aside). A
question of fact is answered from the set by lines cited by source, and the agreement of the
sources is computed. A sort uses the sort of the Assistant; nothing leaves the set.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from otlet.assistant.application.assistant import AssistantStore, Candidate
from otlet.assistant.application.dossiers import Model
from otlet.assistant.domain.qualify import (
    BATCH,
    NO_SUMMARY,
    NOT_JUDGED,
    QUALIFY_SCHEMA,
    QUALIFY_SYSTEM,
    Judged,
    Line,
    check_qualify,
    qualify_message,
    read_qualify,
)
from otlet.assistant.domain.terms import (
    Concept,
    TermsError,
    Widened,
    publisher_country,
    too_general,
    widen,
)
from otlet.reporter.domain.facts import (
    ARTICLES,
    FACT_SCHEMA,
    FACT_SYSTEM,
    Article,
    Fact,
    check_fact,
    fact_message,
    merged,
    read_fact,
    reading_order,
)
from otlet.reporter.domain.questions import (
    CONCEPTS_MAX,
    OPERATION_SCHEMA,
    OPERATION_SYSTEM,
    PROMPT_VERSION,
    QUESTION_MAX_LENGTH,
    TERMS_MAX,
    Operation,
    State,
    Translated,
    about_the_set,
    changes_set,
    check_operation,
    guarded,
    next_state,
    only_false_friends,
    operation_message,
    points_back,
    read_operation,
)
from otlet.reporter.domain.reading import (
    READ_MAX,
    READING_SCHEMA,
    READING_SYSTEM,
    Coverage,
    Read,
    Reading,
    Round,
    check_reading,
    concluded,
    read_reading,
    reading_message,
)
from otlet.workspaces.domain.model import WorkspaceContext

logger = logging.getLogger(__name__)

ANSWER_TURN = "reporter.answer_turn"
FIRST_SEARCH = (
    "\n\nIl n'y a pas encore d'ensemble d'articles : réponds par l'opération « chercher » et les"
    " concepts du sujet de la question."
)
SET_MAX = 200
# The meaning (ADR-0045, spike of 2026-10-30): the 60 items closest to the question, if at least
# 0.6 close (the relevant items of the bench were above, a question on nothing of the Veille
# stayed below 0.55), fused with the items of the words by reciprocal rank.
NEAR_MAX = 60
NEAR_FLOOR = 0.6
RESTRICT_MAX = 5000
RRF_K = 60
DAYS = 30
OPERATION_OUTPUT_TOKENS = 4096
FACT_OUTPUT_TOKENS = 8192
QUALIFY_OUTPUT_TOKENS = 8192
READING_OUTPUT_TOKENS = 8192


class ReporterError(Exception):
    """A rule of the Reporter was not met; `code` is stable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Turn:
    id: UUID
    position: int
    question: str
    status: str  # pending, done, failed
    operation: Operation | None = None
    # The concepts and language the conversation holds after this turn (State), and the
    # concepts as searched: widened by the glossary, general terms set aside.
    state: State = State()
    concepts: list[Widened] = field(default_factory=list)
    term_counts: dict[str, int] = field(default_factory=dict)
    candidates: list[Candidate] = field(default_factory=list)
    fact: Fact | None = None
    verdicts: dict[UUID, Judged] = field(default_factory=dict)
    # « Vérifier en lisant »: the set read by the model, asked or done (reading.py).
    reading: Reading | None = None
    error: str | None = None
    model: str | None = None
    prompt_version: str = PROMPT_VERSION
    attempts: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Conversation:
    id: UUID
    title: str
    days: int | None
    created_at: datetime | None = None
    turns: list[Turn] = field(default_factory=list)


class ReporterStore(Protocol):
    def start_conversation(
        self, workspace_id: UUID, user_id: UUID, title: str, days: int | None
    ) -> Conversation: ...

    def conversations(self, workspace_id: UUID, user_id: UUID, limit: int) -> list[Conversation]:
        """The recent conversations of the author, without their turns."""
        ...

    def conversation(self, workspace_id: UUID, conversation_id: UUID) -> Conversation | None: ...

    def add_turn(
        self,
        workspace_id: UUID,
        user_id: UUID,
        conversation_id: UUID,
        question: str,
        read: bool = False,
    ) -> Turn:
        """Records the question, pending, and enqueues ANSWER_TURN, in one transaction; `read`
        asks for its set to be read once found."""
        ...

    def save_turn(self, workspace_id: UUID, conversation_id: UUID, turn: Turn) -> None: ...

    def read_further(
        self, workspace_id: UUID, user_id: UUID, conversation_id: UUID, turn_id: UUID
    ) -> Turn:
        """Marks the fact pending again and enqueues ANSWER_TURN, in one transaction."""
        ...

    def request_reading(
        self, workspace_id: UUID, user_id: UUID, conversation_id: UUID, turn_id: UUID
    ) -> Turn:
        """Marks the turn pending, its reading asked, and enqueues ANSWER_TURN, in one
        transaction."""
        ...

    def articles(self, workspace_id: UUID, item_ids: list[UUID]) -> list[Article]:
        """The text of the items, in the order given (title first)."""
        ...


def _checked_question(question: str) -> str:
    question = " ".join(question.split())
    if not 1 <= len(question) <= QUESTION_MAX_LENGTH:
        raise ReporterError(
            "invalid_question", f"a question has 1 to {QUESTION_MAX_LENGTH} characters"
        )
    return question


class Reporter:
    def __init__(
        self,
        store: ReporterStore,
        search: AssistantStore,
        model: Model | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        encode: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._store = store
        self._search = search
        self._model = model
        self._now = now
        # The meaning of a question (ADR-0045), in the worker only: the API has no model, and
        # reuses the meaning kept in the state when the author changes the terms.
        self._encode = encode

    # The API --------------------------------------------------------------------------------

    def start(self, context: WorkspaceContext, question: str, read: bool = False) -> Conversation:
        question = _checked_question(question)
        conversation = self._store.start_conversation(
            context.workspace_id, context.user_id, question[:200], DAYS
        )
        turn = self._store.add_turn(
            context.workspace_id, context.user_id, conversation.id, question, read
        )
        return replace(conversation, turns=[turn])

    def ask(
        self, context: WorkspaceContext, conversation_id: UUID, question: str, read: bool = False
    ) -> Turn:
        question = _checked_question(question)
        conversation = self._store.conversation(context.workspace_id, conversation_id)
        if conversation is None:
            raise ReporterError("not_found", "no such conversation")
        if any(turn.status == "pending" for turn in conversation.turns):
            # A question reads the set the previous one leaves: one at a time.
            raise ReporterError("turn_pending", "the previous question is still being answered")
        return self._store.add_turn(
            context.workspace_id, context.user_id, conversation_id, question, read
        )

    def read_more(self, context: WorkspaceContext, conversation_id: UUID, turn_id: UUID) -> Turn:
        """A fact read further: the next ARTICLES items of the set, by the same order."""
        conversation = self._store.conversation(context.workspace_id, conversation_id)
        if conversation is None:
            raise ReporterError("not_found", "no such conversation")
        if any(turn.status == "pending" for turn in conversation.turns):
            raise ReporterError("turn_pending", "the previous question is still being answered")
        turn = next((t for t in conversation.turns if t.id == turn_id), None)
        if turn is None or turn.fact is None or len(turn.fact.read) >= len(turn.candidates):
            raise ReporterError("nothing_more", "every item of the set has been read")
        return self._store.read_further(
            context.workspace_id, context.user_id, conversation_id, turn_id
        )

    def read_set(self, context: WorkspaceContext, conversation_id: UUID, turn_id: UUID) -> Turn:
        """« Vérifier en lisant »: the set of an answered turn read by the model, once."""
        conversation = self._store.conversation(context.workspace_id, conversation_id)
        if conversation is None:
            raise ReporterError("not_found", "no such conversation")
        if any(turn.status == "pending" for turn in conversation.turns):
            raise ReporterError("turn_pending", "the previous question is still being answered")
        turn = next((t for t in conversation.turns if t.id == turn_id), None)
        if turn is None or turn.status != "done" or turn.operation is None:
            raise ReporterError("not_found", "no such answered question")
        if turn.reading is not None and turn.reading.rounds:
            raise ReporterError("already_read", "this set has been read")
        return self._store.request_reading(
            context.workspace_id, context.user_id, conversation_id, turn_id
        )

    def get(self, context: WorkspaceContext, conversation_id: UUID) -> Conversation | None:
        return self._store.conversation(context.workspace_id, conversation_id)

    def recent(self, context: WorkspaceContext, limit: int = 30) -> list[Conversation]:
        return self._store.conversations(context.workspace_id, context.user_id, limit)

    def set_terms(
        self,
        context: WorkspaceContext,
        conversation_id: UUID,
        turn_id: UUID,
        concepts: list[Concept],
    ) -> Turn:
        """The author's terms for the last set of the conversation; the set is found again,
        without a model (the terms stay visible and editable, ADR-0044 §3)."""
        conversation = self._store.conversation(context.workspace_id, conversation_id)
        if conversation is None or not conversation.turns:
            raise ReporterError("not_found", "no such conversation")
        last = conversation.turns[-1]
        if last.id != turn_id or last.status != "done" or not last.state.concepts:
            raise ReporterError("not_editable", "only the terms of the last set can be changed")
        checked = _checked(concepts)
        # The meaning of the question stays: the author changed the words, not the question.
        state = replace(last.state, concepts=checked, subject=min(last.state.subject, len(checked)))
        turn = self._found(context.workspace_id, conversation, last, state)
        self._store.save_turn(context.workspace_id, conversation_id, turn)
        return turn

    # The worker -----------------------------------------------------------------------------

    def run(self, workspace_id: UUID, user_id: UUID, conversation_id: UUID, turn_id: UUID) -> None:
        if self._model is None:
            raise RuntimeError("the model is only reached from the worker")
        conversation = self._store.conversation(workspace_id, conversation_id)
        if conversation is None:
            return
        position = next((n for n, t in enumerate(conversation.turns) if t.id == turn_id), None)
        if position is None or conversation.turns[position].status != "pending":
            return
        turn = conversation.turns[position]
        if turn.reading is not None and turn.reading.requested and turn.operation is not None:
            self._read_saved(workspace_id, user_id, conversation, turn)
            return
        if turn.fact is not None:
            self._read_further(workspace_id, user_id, conversation, turn)
            return
        earlier = [t for t in conversation.turns[:position] if t.status == "done"]
        previous = earlier[-1] if earlier else None
        history = [t.question for t in conversation.turns[:position]]
        attempts: list[dict[str, Any]] = []
        models: list[str] = []
        errors: list[str] = []
        state = previous.state if previous else State()

        raw = None
        # A thinking model may spend its whole answer reasoning (« out_of_room »): asked again,
        # the same question was answered in 33 s (Joël, 2026-10-25). Once more, then no more.
        for _ in range(2):
            raw = self._ask(
                user_id,
                OPERATION_SYSTEM,
                operation_message(history, state, turn.question),
                OPERATION_SCHEMA,
                check_operation,
                OPERATION_OUTPUT_TOKENS,
                (attempts, models, errors),
            )
            if raw is not None or not any("out_of_room" in e for e in errors):
                break
        today = self._now().date()
        if raw is not None:
            translated = guarded(turn.question, read_operation(raw), today)
            if about_the_set(turn.question, translated, state):
                # Asked of the set, answered from it: its articles that truly treat the subject.
                translated = replace(translated, operation=Operation.TRIER, concepts=())
            elif (
                translated.operation is Operation.CHERCHER
                and state.concepts
                and points_back(turn.question)
            ):
                # « Qu'en pensent les enseignants ? »: within the set, not a new subject.
                translated = replace(translated, operation=Operation.RESTREINDRE)
            if not state.concepts and not changes_set(translated.operation):
                # A fact asked first (« Quels sont les derniers faits concernant
                # l'enseignement ? », Joël, 2026-10-29): there is no set yet to read. The set is
                # searched first, then the fact read in it.
                translated = self._search_first(
                    user_id, history, turn.question, translated, today, (attempts, models, errors)
                )
        else:
            # The question itself was searched as one term before: it found nothing, and said
            # nothing of why. The turn fails, and says so.
            self._store.save_turn(
                workspace_id,
                conversation_id,
                replace(
                    turn,
                    status="failed",
                    state=state,
                    error="; ".join(dict.fromkeys(errors)) or "no answer",
                    attempts=attempts,
                    finished_at=self._now(),
                ),
            )
            return

        new_state = (
            next_state(state, translated)
            if changes_set(translated.operation) or state.concepts
            else State(translated.concepts[:3], None, translated.days)
        )
        if new_state.concepts and (
            translated.operation is Operation.CHERCHER or not state.concepts
        ):
            new_state = replace(
                new_state,
                meaning=self._meaning(turn.question),
                subject=len(new_state.concepts),
            )
        done = replace(turn, operation=translated.operation, attempts=attempts)
        if changes_set(translated.operation) or previous is None:
            done = self._found(workspace_id, conversation, done, new_state)
        else:
            done = replace(
                done,
                state=previous.state,
                concepts=previous.concepts,
                term_counts=previous.term_counts,
                candidates=previous.candidates,
            )
        if translated.operation is Operation.FAIT and done.candidates:
            fact = self._fact(workspace_id, user_id, history, done, (attempts, models, errors))
            done = replace(done, fact=fact)
        elif translated.operation is Operation.TRIER and done.candidates:
            subject = " ".join(c.concept.name for c in done.concepts) or turn.question
            verdicts = self._sort(user_id, subject, done.candidates, (attempts, models, errors))
            done = replace(done, verdicts=verdicts)
        if turn.reading is not None and turn.reading.requested:
            # « Lire avant de répondre »: the set is read before the answer is shown.
            reading = self._read(
                workspace_id, user_id, conversation, done, (attempts, models, errors)
            )
            done = replace(done, reading=reading)
        self._store.save_turn(
            workspace_id,
            conversation_id,
            replace(
                done,
                status="done",
                error="; ".join(dict.fromkeys(errors)) or None,
                model=", ".join(dict.fromkeys(models)) or None,
                attempts=attempts,
                finished_at=self._now(),
            ),
        )

    # Inside ---------------------------------------------------------------------------------

    def _search_first(
        self,
        user_id: UUID,
        history: list[str],
        question: str,
        translated: Translated,
        today: date,
        log: tuple[list[dict[str, Any]], list[str], list[str]],
    ) -> Translated:
        """The concepts of a first question that is not a search: the model's own when it gave
        some, else asked again as a search. The operation stays what the author asked."""
        if translated.concepts:
            return translated
        raw = self._ask(
            user_id,
            OPERATION_SYSTEM,
            operation_message(history, State(), question) + FIRST_SEARCH,
            OPERATION_SCHEMA,
            check_operation,
            OPERATION_OUTPUT_TOKENS,
            log,
        )
        if raw is None:
            return translated
        searched = guarded(question, read_operation(raw), today, every_word=False)
        return replace(
            translated, concepts=searched.concepts, days=translated.days or searched.days
        )

    def _found(
        self, workspace_id: UUID, conversation: Conversation, turn: Turn, state: State
    ) -> Turn:
        """The set of the state: concepts widened by the glossary, general terms set aside,
        items holding a term of every concept, in the language asked. No model."""
        if not state.concepts:
            return replace(turn, state=state, concepts=[], term_counts={}, candidates=[])
        widened, counts, found = self._search_set(workspace_id, conversation, state)
        return replace(turn, state=state, concepts=widened, term_counts=counts, candidates=found)

    def _search_set(
        self, workspace_id: UUID, conversation: Conversation, state: State
    ) -> tuple[list[Widened], dict[str, int], list[Candidate]]:
        glossary = [stored.entry for stored in self._search.glossary(workspace_id)]
        days = state.days or conversation.days
        since = None if days is None else self._now() - timedelta(days=days)
        widened = widen(list(state.concepts), glossary)
        counts = self._search.term_counts(
            workspace_id, [term for w in widened for term in w.all_terms], since
        )
        widened = too_general(widened, counts, self._search.total_items(workspace_id, since))
        found = self._search.candidates(workspace_id, widened, since, SET_MAX)
        if state.meaning:
            found = self._with_meaning(workspace_id, state, widened, since, found)
        found = [
            c
            for c in found
            if not any(only_false_friends(f"{c.title} {c.summary}", w.terms) for w in widened)
        ]
        if state.language:
            found = [c for c in found if (c.language or "").startswith(state.language)]
        return widened, counts, found

    def _meaning(self, question: str) -> tuple[float, ...]:
        """The vector of a question, or none when the encoder is missing or fails: the words
        alone then, as before ADR-0045."""
        if self._encode is None:
            return ()
        try:
            return tuple(self._encode(question))
        except Exception:  # noqa: BLE001 (the meaning adds; its failure takes nothing away)
            logger.warning("the meaning of a question could not be encoded", exc_info=True)
            return ()

    def _with_meaning(
        self,
        workspace_id: UUID,
        state: State,
        widened: list[Widened],
        since: datetime | None,
        found: list[Candidate],
    ) -> list[Candidate]:
        """The items of the words and the items closest to the question, ranked together by
        reciprocal rank (ADR-0045). An item found by the meaning must hold the concepts that
        restricted the search since (« uniquement en Belgique »)."""
        near = self._search.near(workspace_id, state.meaning, since, NEAR_MAX, NEAR_FLOOR)
        restrictions = widened[state.subject :]
        if near and restrictions:
            allowed = {
                c.id
                for c in self._search.candidates(workspace_id, restrictions, since, RESTRICT_MAX)
            }
            near = [c for c in near if c.id in allowed]
        scores: dict[UUID, float] = {}
        by_id: dict[UUID, Candidate] = {}
        for ranked in (found, near):
            for rank, candidate in enumerate(ranked):
                scores[candidate.id] = scores.get(candidate.id, 0.0) + 1 / (RRF_K + rank)
                by_id.setdefault(candidate.id, candidate)
        return [by_id[i] for i in sorted(scores, key=lambda i: -scores[i])][:SET_MAX]

    def _read(
        self,
        workspace_id: UUID,
        user_id: UUID,
        conversation: Conversation,
        turn: Turn,
        log: tuple[list[dict[str, Any]], list[str], list[str]],
    ) -> Reading:
        """The set read as a person reads it: the first READ_MAX items judged; when the
        question is not covered, one more search with the model's terms, read the same way."""
        history = [t.question for t in conversation.turns if t.position < turn.position]
        errors_before = len(log[2])
        first_items = [_read_item(c) for c in turn.candidates[:READ_MAX]]
        rounds = [
            Round(turn.state.concepts, tuple(r.item_id for r in first_items), len(turn.candidates))
        ]
        raw = self._ask_reading(user_id, history, turn.question, first_items, log)
        if raw is None:
            return Reading(errors=tuple(log[2][errors_before:]))
        first = read_reading(raw, first_items, 1)
        second = None
        if first.coverage is not Coverage.OUI and first.others:
            state = State(first.others, turn.state.language, turn.state.days)
            _, _, found = self._search_set(workspace_id, conversation, state)
            seen = {r.item_id for r in first_items}
            fresh = [_read_item(c) for c in found if str(c.id) not in seen][:READ_MAX]
            rounds.append(Round(first.others, tuple(r.item_id for r in fresh), len(found)))
            if fresh:
                again = self._ask_reading(user_id, history, turn.question, fresh, log)
                second = read_reading(again, fresh, 2) if again is not None else None
        coverage, missing = concluded(first, second)
        answers = first.answers + (second.answers if second is not None else ())
        return Reading(
            False, tuple(rounds), answers, coverage, missing, tuple(log[2][errors_before:])
        )

    def _ask_reading(
        self,
        user_id: UUID,
        history: list[str],
        question: str,
        items: list[Read],
        log: tuple[list[dict[str, Any]], list[str], list[str]],
    ) -> str | None:
        return self._ask(
            user_id,
            READING_SYSTEM,
            reading_message(history, question, items),
            READING_SCHEMA,
            check_reading,
            READING_OUTPUT_TOKENS,
            log,
        )

    def _read_saved(
        self, workspace_id: UUID, user_id: UUID, conversation: Conversation, turn: Turn
    ) -> None:
        attempts: list[dict[str, Any]] = []
        models: list[str] = []
        errors: list[str] = []
        reading = self._read(workspace_id, user_id, conversation, turn, (attempts, models, errors))
        self._store.save_turn(
            workspace_id,
            conversation.id,
            replace(
                turn,
                status="done",
                reading=reading,
                model=", ".join(dict.fromkeys(models)) or turn.model,
                attempts=[*turn.attempts, *attempts],
                finished_at=self._now(),
            ),
        )

    def _fact(
        self,
        workspace_id: UUID,
        user_id: UUID,
        history: list[str],
        turn: Turn,
        log: tuple[list[dict[str, Any]], list[str], list[str]],
    ) -> Fact | None:
        order = reading_order(turn.question, [f"{c.title} {c.summary}" for c in turn.candidates])
        done = set(turn.fact.read) if turn.fact is not None else set()
        chosen = [turn.candidates[n].id for n in order if str(turn.candidates[n].id) not in done]
        articles = self._store.articles(workspace_id, chosen[:ARTICLES])
        raw = self._ask(
            user_id,
            FACT_SYSTEM,
            fact_message(history, turn.question, articles),
            FACT_SCHEMA,
            check_fact,
            FACT_OUTPUT_TOKENS,
            log,
        )
        if raw is None:
            return None
        glossary = [stored.entry for stored in self._search.glossary(workspace_id)]
        return read_fact(raw, articles, glossary)

    def _read_further(
        self, workspace_id: UUID, user_id: UUID, conversation: Conversation, turn: Turn
    ) -> None:
        attempts: list[dict[str, Any]] = []
        models: list[str] = []
        errors: list[str] = []
        history = [t.question for t in conversation.turns if t.position < turn.position]
        more = self._fact(workspace_id, user_id, history, turn, (attempts, models, errors))
        glossary = [stored.entry for stored in self._search.glossary(workspace_id)]
        fact = turn.fact if more is None or turn.fact is None else merged(turn.fact, more, glossary)
        self._store.save_turn(
            workspace_id,
            conversation.id,
            replace(
                turn,
                status="done",
                fact=fact,
                error="; ".join(dict.fromkeys(errors)) or None,
                model=", ".join(dict.fromkeys(models)) or turn.model,
                attempts=[*turn.attempts, *attempts],
                finished_at=self._now(),
            ),
        )

    def _sort(
        self,
        user_id: UUID,
        subject: str,
        candidates: list[Candidate],
        log: tuple[list[dict[str, Any]], list[str], list[str]],
    ) -> dict[UUID, Judged]:
        """The sort of the Assistant de veille (ADR-0043 §5): nothing is excluded."""
        verdicts: dict[UUID, Judged] = {}
        sent = []
        for candidate in candidates:
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
                qualify_message(subject, "", lines),
                QUALIFY_SCHEMA,
                check_qualify,
                QUALIFY_OUTPUT_TOKENS,
                log,
            )
            judged = read_qualify(raw, len(batch)) if raw is not None else {}
            for n, candidate in enumerate(batch, 1):
                verdicts[candidate.id] = judged.get(n, NOT_JUDGED)
        return verdicts

    def _ask(
        self,
        user_id: UUID,
        system: str,
        user: str,
        schema: dict[str, Any],
        validate: Callable[[str], list[str]],
        max_output_tokens: int,
        log: tuple[list[dict[str, Any]], list[str], list[str]],
    ) -> str | None:
        if self._model is None:
            raise RuntimeError("the model is only reached from the worker")
        attempts, models, errors = log
        asked = self._model.ask(user_id, system, user, schema, validate, max_output_tokens)
        attempts.extend(asked.attempts)
        if asked.model:
            models.append(asked.model)
        if asked.text is None:
            errors.append(asked.error or "no answer")
        return asked.text


def _read_item(candidate: Candidate) -> Read:
    return Read(
        str(candidate.id),
        candidate.title,
        candidate.summary,
        candidate.publisher or "",
        candidate.dated.isoformat(),
        candidate.url,
    )


def _checked(concepts: list[Concept]) -> tuple[Concept, ...]:
    """The author's concepts: one to four, each with one to twenty terms."""
    out = []
    for concept in concepts:
        terms = tuple(dict.fromkeys(" ".join(t.split()) for t in concept.terms if t.strip()))
        if not 1 <= len(terms) <= TERMS_MAX:
            raise TermsError("invalid_terms", f"a concept has 1 to {TERMS_MAX} terms")
        out.append(Concept(" ".join(concept.name.split()) or terms[0], terms))
    if not 1 <= len(out) <= CONCEPTS_MAX:
        raise TermsError("invalid_concepts", f"a set has 1 to {CONCEPTS_MAX} concepts")
    return tuple(out)
