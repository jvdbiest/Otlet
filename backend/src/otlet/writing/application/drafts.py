# SPDX-License-Identifier: AGPL-3.0-or-later
"""Drafts of a brief (U04, F-RED-02, UC « rédiger un article » steps 3 to 6).

« Générer le brouillon » records a generation and enqueues it; the worker sends the brief and
its sources to the model the brief asks for (or the author's profile), checks the answer, and
stores it as a new version of the brief's article. A failed generation says why; the brief is
kept as it was.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.domain.article import Article, Generation
from otlet.writing.domain.brief import Brief, ModelChoice
from otlet.writing.domain.draft import (
    WORDS,
    SourceText,
    check_answer,
    messages,
    output_schema,
    prompt_sources,
    source_budget,
    to_document,
)

GENERATE_DRAFT = "writing.generate_draft"
# Room for the answer: about two tokens a word, plus the JSON around the text.
OUTPUT_TOKENS = {length: words * 2 + 600 for length, words in WORDS.items()}
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
        """The window of the first model to be tried (tokens, 0 when unknown), and whether it
        runs on a local engine."""
        ...

    def write(
        self,
        user_id: UUID,
        prompt: list[tuple[str, str]],
        schema: dict[str, Any],
        validate: Callable[[str], list[str]],
        model: ModelChoice | None,
        max_output_tokens: int,
    ) -> Written: ...


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
    ) -> tuple[UUID, int]:
        """Creates the article of the brief if needed, adds the version; (article, number)."""
        ...

    def finish(
        self,
        workspace_id: UUID,
        generation_id: UUID,
        error: str | None,
        attempts: Sequence[dict[str, Any]],
        article: tuple[UUID, int] | None,
    ) -> None: ...

    def article_of(self, workspace_id: UUID, brief_id: UUID) -> Article | None: ...


class BriefSource(Protocol):
    def get_brief(self, workspace_id: UUID, brief_id: UUID) -> Brief | None: ...


class Drafts:
    def __init__(
        self, briefs: BriefSource, articles: ArticleStore, writer: Writer | None = None
    ) -> None:
        """The API passes no writer: it only records generations; the worker writes them."""
        self._briefs = briefs
        self._articles = articles
        self._writer = writer

    def start(self, context: WorkspaceContext, brief_id: UUID) -> Generation | None:
        """None when the brief does not exist; a generation already running is returned as is."""
        if self._briefs.get_brief(context.workspace_id, brief_id) is None:
            return None
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
            self._articles.finish(workspace_id, generation_id, "no_sources", (), None)
            return
        fields = brief.fields
        context_tokens, local = writer.room(user_id, fields.model)
        sources = prompt_sources(texts, source_budget(context_tokens, local))
        keys = [source.key for source in sources]
        written = writer.write(
            user_id,
            messages(fields, sources),
            output_schema(keys),
            lambda raw: check_answer(raw, keys),
            fields.model,
            OUTPUT_TOKENS[fields.length],
        )
        if written.text is None:
            self._articles.finish(
                workspace_id, generation_id, written.error or "unavailable", written.attempts, None
            )
            return
        title, document = to_document(written.text, sources, fields.language)
        cut = [source.key for source in sources if source.cut]
        made = self._articles.add_version(
            workspace_id, user_id, generation.brief_id, title, document, written, cut
        )
        self._articles.finish(workspace_id, generation_id, None, written.attempts, made)
