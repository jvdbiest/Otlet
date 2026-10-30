# SPDX-License-Identifier: AGPL-3.0-or-later
"""Drafts of a brief (U04, F-RED-02, UC « rédiger un article » steps 3 to 6).

« Générer le brouillon » records a generation and enqueues it; the worker sends the brief and
its sources to the model the brief asks for (or the author's profile), checks the answer, and
stores it as a new version of the brief's article. A failed generation says why; the brief is
kept as it was.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.domain.article import Article, Generation
from otlet.writing.domain.brief import Brief, BriefFields, Length, Mode, ModelChoice
from otlet.writing.domain.draft import (
    CHARS_PER_TOKEN,
    PROMPT_VERSION,
    WORDS,
    SourceText,
    asks_dates,
    asks_order,
    check_answer,
    cited_keys,
    dated_headings,
    in_order,
    lone_sections,
    longest_for,
    matter_level,
    messages,
    output_schema,
    prompt_sources,
    repeated_paragraphs,
    source_budget,
    to_document,
    without_copied_passages,
    without_repeats,
)
from otlet.writing.domain.guardrails import copied_sequences, copying, unsupported
from otlet.writing.domain.vocabulary import choice

GENERATE_DRAFT = "writing.generate_draft"


class MatterError(Exception):
    """The sources of the brief hold too little for a draft: generated only on confirmation."""

    def __init__(self, words: int) -> None:
        super().__init__(f"{words} words of sources: too few for a draft")
        self.words = words


# Room for the answer: about three tokens a word, plus the JSON around the text and what a
# « thinking » model (qwen3) writes before answering. A short draft cut at 1,200 tokens was
# seen (Joël's case, 2026-10-17).
OUTPUT_TOKENS = {length: words * 3 + 1000 for length, words in WORDS.items()}
# A local model costs nothing per token, and a « thinking » one (qwen3, gemma4) spends its
# output on reasoning first: gemma4 was cut mid-answer under 1,900 tokens. It gets more room.
LOCAL_OUTPUT_TOKENS = 8192
# A local model on a small machine writes slowly: a draft may take minutes.
TIMEOUT_SECONDS = 600.0


@dataclass(frozen=True, slots=True)
class Written:
    """What the writer got from the models: the answer, or why there is none."""

    text: str | None
    error: str | None
    provider_kind: str | None
    model: str | None
    attempts: tuple[dict[str, Any], ...]


class Writer(Protocol):
    """The AI gateway, as the writing module sees it."""

    def room(self, user_id: UUID, model: ModelChoice | None) -> tuple[int, bool]:
        """The context window of the first model to be tried, in tokens (the provider's
        setting, the catalogue, or the default of a local engine), and whether it is local."""
        ...

    def write(
        self,
        user_id: UUID,
        prompt: list[tuple[str, str]],
        schema: dict[str, Any],
        validate: Callable[[str], list[str]],
        model: ModelChoice | None,
        max_output_tokens: int,
        cancelled: Callable[[], bool] | None = None,
    ) -> Written: ...


@dataclass(frozen=True, slots=True)
class RunningDraft:
    brief_id: UUID
    title: str
    created_at: datetime


class ArticleStore(Protocol):
    def start(self, workspace_id: UUID, user_id: UUID, brief_id: UUID) -> Generation:
        """Records a running generation and enqueues its job, in one transaction."""
        ...

    def generation(self, workspace_id: UUID, generation_id: UUID) -> Generation | None: ...

    def latest_generation(self, workspace_id: UUID, brief_id: UUID) -> Generation | None: ...

    def sources(self, workspace_id: UUID, brief_id: UUID) -> list[SourceText]:
        """The items of the brief in order, each with the text Otlet may send to a model."""
        ...

    def add_version(
        self,
        workspace_id: UUID,
        user_id: UUID,
        brief_id: UUID,
        title: str,
        document: dict[str, Any],
        written: Written,
        cut_sources: Sequence[str],
        unused_sources: Sequence[str],
        context_overflow: bool,
    ) -> tuple[UUID, int]:
        """Creates the article of the brief if needed, adds the version; (article, number).
        `cut_sources` and `unused_sources`: titles of items of the brief whose text was cut,
        or that the draft does not cite."""
        ...

    def finish(
        self,
        workspace_id: UUID,
        generation_id: UUID,
        error: str | None,
        attempts: Sequence[dict[str, Any]],
        article: tuple[UUID, int] | None,
        details: dict[str, Any],
    ) -> None: ...

    def clear_details(self, workspace_id: UUID, brief_id: UUID) -> int:
        """Empties the details and attempts of the generations of the brief; how many."""
        ...

    def cancel(self, workspace_id: UUID, brief_id: UUID) -> Generation | None:
        """Ends the running generation of the brief as cancelled; None when none runs."""
        ...

    def article_of(self, workspace_id: UUID, brief_id: UUID) -> Article | None: ...

    def running(self, workspace_id: UUID, user_id: UUID) -> list[RunningDraft]: ...


class BriefSource(Protocol):
    def get_brief(self, workspace_id: UUID, brief_id: UUID) -> Brief | None: ...


class Drafts:
    def __init__(
        self,
        briefs: BriefSource,
        articles: ArticleStore,
        writer: Writer | None = None,
        charter: Callable[[UUID], str] | None = None,
    ) -> None:
        """The API passes no writer: it only records generations; the worker writes them.
        `charter` gives the writing charter of a user (none when not given)."""
        self._briefs = briefs
        self._articles = articles
        self._writer = writer
        self._charter = charter or (lambda user_id: "")

    def start(
        self, context: WorkspaceContext, brief_id: UUID, *, force: bool = False
    ) -> Generation | None:
        """None when the brief does not exist; a generation already running is returned as is.
        Sources too thin for a draft are refused unless the author confirms (`force`)."""
        brief = self._briefs.get_brief(context.workspace_id, brief_id)
        if brief is None:
            return None
        if not force and matter_level(brief.matter_words, brief.full_text) == "insufficient":
            raise MatterError(brief.matter_words)
        running = self._articles.latest_generation(context.workspace_id, brief_id)
        if running is not None and running.status == "running":
            return running
        return self._articles.start(context.workspace_id, context.user_id, brief_id)

    def generation(self, context: WorkspaceContext, generation_id: UUID) -> Generation | None:
        return self._articles.generation(context.workspace_id, generation_id)

    def latest_generation(self, context: WorkspaceContext, brief_id: UUID) -> Generation | None:
        return self._articles.latest_generation(context.workspace_id, brief_id)

    def article(self, context: WorkspaceContext, brief_id: UUID) -> Article | None:
        return self._articles.article_of(context.workspace_id, brief_id)

    def sources(self, context: WorkspaceContext, brief_id: UUID) -> list[SourceText] | None:
        """The texts of the brief's items as a draft receives them, in its order: the reference
        of « Comparer » (Joël, 2026-10-20). None when the brief does not exist."""
        if self._briefs.get_brief(context.workspace_id, brief_id) is None:
            return None
        return self._articles.sources(context.workspace_id, brief_id)

    def cancel(self, context: WorkspaceContext, brief_id: UUID) -> Generation | None:
        """Cancels the running draft of a brief (Joël, 2026-10-18): nothing of it is kept. The
        worker cuts its call to the model (Joël, 2026-10-30)."""
        return self._articles.cancel(context.workspace_id, brief_id)

    def running(self, context: WorkspaceContext) -> list[RunningDraft]:
        return self._articles.running(context.workspace_id, context.user_id)

    def clear_details(self, context: WorkspaceContext, brief_id: UUID) -> int | None:
        """Empties the details of the drafts of a brief; None when the brief does not exist."""
        if self._briefs.get_brief(context.workspace_id, brief_id) is None:
            return None
        return self._articles.clear_details(context.workspace_id, brief_id)

    def _cancelled(self, workspace_id: UUID, generation_id: UUID) -> bool:
        current = self._articles.generation(workspace_id, generation_id)
        return current is None or current.status != "running"

    def run(self, workspace_id: UUID, user_id: UUID, generation_id: UUID) -> None:
        """The job: writes the draft, or records why it could not."""
        writer = self._writer
        if writer is None:
            raise RuntimeError("drafts are written by the worker, which has a writer")
        generation = self._articles.generation(workspace_id, generation_id)
        if generation is None or generation.status != "running":
            return
        brief = self._briefs.get_brief(workspace_id, generation.brief_id)
        texts = self._articles.sources(workspace_id, generation.brief_id)
        if brief is None or not texts:
            self._articles.finish(workspace_id, generation_id, "no_sources", (), None, {})
            return
        # The length the sources can carry (Joël, 2026-10-19, after the audit): never more than
        # asked, never more than their words hold; thin sources get a short draft and a warning.
        matter = sum(len(text.text.split()) for text in texts)
        longest = longest_for(matter)
        level = matter_level(matter, any(item.full_text for item in brief.items))
        asked = brief.fields.length
        used = Length.SHORT if longest is None else min(asked, longest, key=WORDS.__getitem__)
        fields = replace(brief.fields, length=used)
        window, local = writer.room(user_id, fields.model)
        output = OUTPUT_TOKENS[fields.length]
        charter = self._charter(user_id)
        chosen = {f: choice(f, getattr(fields, f)) for f in ("audience", "tone", "channel")}
        # The charter takes room in the window too: as much less for the sources.
        budget = max(source_budget(window, output) - len(charter), 0)
        sources = prompt_sources(texts, budget, f"{fields.title} {fields.angle}")
        keys = [source.key for source in sources]
        copied_from = copied_sequences([f"{text.title}\n{text.text}" for text in texts])
        checks = 0
        dated = asks_dates(fields)
        refusals: list[list[str]] = []

        def validate(raw: str) -> list[str]:
            # An answer that leaves a source out is sent back once by the gateway, with those
            # sources, to add them if they speak to the subject. The repaired answer is kept even
            # if it still leaves some out: the version then says which (a warning, not a failure).
            nonlocal checks
            checks += 1
            first = checks == 1
            # Crossing the sources is no longer sent back (Joël, 2026-10-19): forced, it made
            # the model invent links; the sections on one source stay a warning.
            found = check_answer(
                raw,
                keys,
                every_source=first,
                crossing=False,
                words=WORDS[fields.length],
                repeats=first,
                in_text=first,
                dates=first and dated,
                copied_from=copied_from if first else frozenset(),
            )
            refusals.append(found)
            return found

        written = writer.write(
            user_id,
            messages(fields, sources, charter),
            output_schema(keys),
            validate,
            fields.model,
            max(output, LOCAL_OUTPUT_TOKENS if local else 0),
            lambda: self._cancelled(workspace_id, generation_id),
        )
        details = {
            "brief": {
                "mode": fields.mode.value,
                "length": asked.value,
                "length_used": used.value,
                "language": fields.language,
                "model": "profile" if fields.model is None else fields.model.model,
                "angle": fields.angle,
                "instructions": fields.instructions,
                "charter": charter,
                # The labels, as the details show them; the keys and definitions sent, to
                # compare generations on the same terms (Joël, 2026-10-19).
                **{field: found.label if found else "" for field, found in chosen.items()},
                "choices": {
                    field: {"key": found.key, "label": found.label, "definition": found.definition}
                    for field, found in chosen.items()
                    if found is not None
                },
            },
            "prompt_version": PROMPT_VERSION,
            "window_tokens": window,
            "local": local,
            "output_tokens": output,
            "charter_tokens": -(-len(charter) // CHARS_PER_TOKEN),
            "matter_words": matter,
            "matter_level": level,
            "thin_matter": longest is None,
            "source_room_chars": budget,
            "sources": [
                {
                    "key": s.key,
                    "title": s.source.title,
                    "chars": len(s.source.text),
                    "words": len(s.source.text.split()),
                    "sent": len(s.text),
                    "cut": s.cut,
                }
                for s in sources
            ],
            "refusals": [errors for errors in refusals if errors],
            "attempts": list(written.attempts),
        }
        if written.text is None:
            self._articles.finish(
                workspace_id,
                generation_id,
                written.error or "unavailable",
                written.attempts,
                None,
                details,
            )
            return
        # A section the model copied is taken out; the details say what was (Joël, 2026-10-25).
        answer = without_repeats(written.text)
        answer, removed = without_copied_passages(answer, copied_from)
        if dated:
            # Asked dates the model left out: the date of the source, without a model.
            answer = dated_headings(answer, sources, fields.language)
        if asks_order(fields):
            answer = in_order(answer)
        title, document = to_document(answer, sources, fields.language)
        cut = [source.source.title for source in sources if source.cut]
        cited = cited_keys(answer)
        unused = [source.source.title for source in sources if source.key not in cited]
        # More tokens than the window: a local engine may have dropped the start of the
        # conversation, where the rules are (Ollama does so without a word).
        last = written.attempts[-1] if written.attempts else {}
        overflow = int(last.get("tokens_in", 0)) + int(last.get("tokens_out", 0)) > window
        still = self._articles.generation(workspace_id, generation_id)
        if still is None or still.status != "running":
            return  # cancelled while the model wrote: nothing is kept
        made = self._articles.add_version(
            workspace_id,
            user_id,
            generation.brief_id,
            title,
            document,
            written,
            cut,
            unused,
            overflow,
        )
        details["context_overflow"] = overflow
        if fields.mode is Mode.SYNTHESIS and len(keys) > 1:
            # The repaired answer is kept even if some sections still draw on one source:
            # the version says which (a warning, not a failure).
            details["lone_sections"] = lone_sections(answer)
        details["repeated_paragraphs"] = repeated_paragraphs(written.text)
        details["copies_removed"] = removed
        details.update(checked(answer, texts, brief.fields))
        self._articles.finish(workspace_id, generation_id, None, written.attempts, made, details)


def checked(raw: str, texts: Sequence[SourceText], fields: BriefFields) -> dict[str, Any]:
    """The guardrails of a model's draft (U05, first batch, Joël, 2026-10-19): its names, dates
    and numbers that no source writes, and what it copies from the sources. The author's own
    words in the brief (title, angle, instructions) are no invention."""
    data = json.loads(raw)
    paragraphs = [data["lead"]] + [p["text"] for s in data["sections"] for p in s["paragraphs"]]
    sources = [f"{text.title}\n{text.text}" for text in texts]
    # Nor are the facts the author verified (ADR-0044 §10).
    verified = [f"{f.figure} {f.measure} {f.when} {f.where}" for f in fields.facts]
    allowed = " ".join([fields.title, fields.angle, fields.instructions, *verified])
    copied = copying(paragraphs, sources)
    return {
        "unsupported": [
            {"kind": f.kind, "text": f.text, "paragraph": f.paragraph}
            for f in unsupported(paragraphs, sources, allowed)
        ],
        "copying": {
            "share": copied.share,
            "passages": [
                {"paragraph": paragraph, "excerpt": excerpt, "words": words}
                for paragraph, excerpt, words in copied.passages
            ],
        },
    }
