# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the briefs (U03, F-RED-01), under a workspace (F03)."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.application.briefs import Briefs
from otlet.writing.application.drafts import Drafts, MatterError
from otlet.writing.application.editing import Editing
from otlet.writing.application.exports import Exports
from otlet.writing.application.library import Library, TagError
from otlet.writing.domain.article import Article, Generation, LibraryEntry, Version
from otlet.writing.domain.brief import (
    ITEMS_MAX,
    Brief,
    BriefError,
    BriefFields,
    BriefItem,
    Length,
    Mode,
    ModelChoice,
)
from otlet.writing.domain.document import body_text
from otlet.writing.domain.draft import (
    MATTER_FLOOR,
    MATTER_SHARE,
    WORDS,
    longest_for,
    matter_level,
)
from otlet.writing.domain.vocabulary import TONE_DEFAULT, VOCABULARY


class BriefItemView(BaseModel):
    id: UUID
    title: str
    url: str | None
    source_id: UUID | None
    source_name: str | None
    published_at: datetime | None
    words: int  # the words a draft may use of it
    full_text: bool  # False: only its summary may be used
    declared: bool  # read under the author's declaration of rights (their responsibility)

    @classmethod
    def of(cls, item: BriefItem) -> "BriefItemView":
        return cls(
            id=item.id,
            title=item.title,
            url=item.url,
            source_id=item.source_id,
            source_name=item.source_name,
            published_at=item.published_at,
            words=item.words,
            full_text=item.full_text,
            declared=item.declared,
        )


class BriefView(BaseModel):
    id: UUID
    title: str
    angle: str
    instructions: str
    audience: str
    tone: str
    length: Literal["short", "medium", "long"]
    mode: Literal["synthesis", "panorama"]
    language: str
    channel: str
    provider_id: UUID | None  # None: the profile of the author
    model: str | None
    items: list[BriefItemView]
    sources: int
    single_source: bool  # fewer than two sources: said, not refused
    matter_words: int  # the words of its sources a draft may use
    matter_level: Literal["enough", "limited", "insufficient"]
    # The longest article they can carry (Joël, 2026-10-19); None: even a short one is thin.
    length_max: Literal["short", "medium", "long"] | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, brief: Brief) -> "BriefView":
        fields = brief.fields
        longest = longest_for(brief.matter_words)
        return cls(
            id=brief.id,
            title=fields.title,
            angle=fields.angle,
            instructions=fields.instructions,
            audience=fields.audience,
            tone=fields.tone,
            length=fields.length.value,
            mode=fields.mode.value,
            language=fields.language,
            channel=fields.channel,
            provider_id=None if fields.model is None else fields.model.provider_id,
            model=None if fields.model is None else fields.model.model,
            items=[BriefItemView.of(item) for item in brief.items],
            sources=brief.sources,
            single_source=brief.single_source,
            matter_words=brief.matter_words,
            matter_level=cast(
                Literal["enough", "limited", "insufficient"],
                matter_level(brief.matter_words, brief.full_text),
            ),
            length_max=None if longest is None else longest.value,
            created_at=brief.created_at,
            updated_at=brief.updated_at,
        )


class SourceTextView(BaseModel):
    """A source of the brief as the drafts receive it: its text Otlet may use, else its summary."""

    key: str  # S1, S2… in the order of the brief
    title: str
    url: str | None
    publisher: str | None
    published_at: datetime | None
    words: int
    text: str


class GenerateBody(BaseModel):
    force: bool = False  # « Générer quand même »: sources too thin, the author confirms


class ChoiceView(BaseModel):
    key: str
    label: str
    definition: str  # what the model receives
    length_max: Literal["short", "medium", "long"] | None  # a channel's longest article


class VocabularyView(BaseModel):
    """The values a brief's audience, tone and channel take (Joël, 2026-10-19, phase 1)."""

    audience: list[ChoiceView]
    tone: list[ChoiceView]
    channel: list[ChoiceView]
    tone_default: str
    # The rule of the length (Joël, 2026-10-19): an article of `length_words` words needs
    # sources of `length_words / matter_share` words at least.
    length_words: dict[str, int]
    matter_share: float
    matter_floor: int  # below, the matter is insufficient (draft.py, matter_level)


class BriefBody(BaseModel):
    title: str
    item_ids: list[UUID] = Field(min_length=1, max_length=ITEMS_MAX)
    angle: str = ""
    instructions: str = ""
    audience: str = ""  # keys of the lists of /brief-vocabulary; "" for none
    tone: str = "neutral"
    length: Literal["short", "medium", "long"] = "medium"
    mode: Literal["synthesis", "panorama"] = "synthesis"
    language: str = "fr"
    channel: str = ""
    provider_id: UUID | None = None  # with `model`; none for the profile of the author
    model: str | None = None

    def fields(self) -> BriefFields:
        return BriefFields(
            title=self.title,
            item_ids=tuple(self.item_ids),
            angle=self.angle,
            instructions=self.instructions,
            audience=self.audience,
            tone=self.tone,
            length=Length(self.length),
            mode=Mode(self.mode),
            language=self.language,
            channel=self.channel,
            model=None
            if self.provider_id is None
            else ModelChoice(self.provider_id, self.model or ""),
        )


class GenerationView(BaseModel):
    id: UUID
    brief_id: UUID
    status: Literal["running", "done", "failed"]
    error: str | None
    version: int | None
    attempts: list[dict[str, Any]]  # provider, model, result, seconds: never the text
    details: dict[str, Any]  # what it was written with: never the prompt nor the answer
    created_at: datetime
    finished_at: datetime | None

    @classmethod
    def of(cls, generation: Generation) -> "GenerationView":
        return cls(
            id=generation.id,
            brief_id=generation.brief_id,
            status=generation.status,
            error=generation.error,
            version=generation.version,
            attempts=list(generation.attempts),
            details=generation.details,
            created_at=generation.created_at,
            finished_at=generation.finished_at,
        )


class VersionView(BaseModel):
    number: int
    title: str
    document: dict[str, Any]  # « Document plateforme v1 » (ADR-0023)
    origin: Literal["ia", "humain"]
    provider_kind: str | None
    model: str | None
    prompt_version: str | None
    cut_sources: list[str]
    unused_sources: list[str]  # items of the brief the draft does not cite
    context_overflow: bool  # the call went past the window: the start may have been dropped
    details: dict[str, Any]  # of the generation that made it; {} once cleared
    created_at: datetime
    updated_at: datetime  # sent back by « Enregistrer »: a version changed since is not saved over
    based_on: int | None  # the version a person's version was made from
    words: int  # of its text (Joël, 2026-10-19: shown beside its number)

    @classmethod
    def of(cls, version: Version) -> "VersionView":
        return cls(
            number=version.number,
            title=version.title,
            document=version.document,
            origin=version.origin,
            provider_kind=version.provider_kind,
            model=version.model,
            prompt_version=version.prompt_version,
            cut_sources=list(version.cut_sources),
            unused_sources=list(version.unused_sources),
            context_overflow=version.context_overflow,
            details=version.details,
            created_at=version.created_at,
            updated_at=version.updated_at or version.created_at,
            based_on=version.based_on,
            words=len(body_text(version.document).split()),
        )


class ArticleView(BaseModel):
    id: UUID
    brief_id: UUID | None
    title: str
    versions: list[VersionView]  # the latest last
    status: Literal["brouillon", "valide", "archive"]
    validated_version: int | None  # the one exports and publications take
    sent_at: datetime | None  # when it entered the Library; None while it is in the workshop
    tags: list[str]

    @classmethod
    def of(cls, article: Article) -> "ArticleView":
        return cls(
            id=article.id,
            brief_id=article.brief_id,
            title=article.title,
            versions=[VersionView.of(v) for v in article.versions],
            status=article.status,
            validated_version=article.validated_version,
            sent_at=article.sent_at,
            tags=list(article.tags),
        )


class LibraryEntryView(BaseModel):
    id: UUID
    brief_id: UUID | None
    title: str
    status: Literal["brouillon", "valide", "archive"]
    validated_version: int | None
    current_version: int
    tags: list[str]
    sent_at: datetime
    updated_at: datetime
    excerpt: str  # « words » searched for are between « and »

    @classmethod
    def of(cls, entry: LibraryEntry) -> "LibraryEntryView":
        return cls(
            id=entry.id,
            brief_id=entry.brief_id,
            title=entry.title,
            status=entry.status,
            validated_version=entry.validated_version,
            current_version=entry.current_version,
            tags=list(entry.tags),
            sent_at=entry.sent_at,
            updated_at=entry.updated_at,
            excerpt=entry.excerpt,
        )


class SendBody(BaseModel):
    number: int  # the version validated


class ArchiveBody(BaseModel):
    archived: bool


class TagsBody(BaseModel):
    tags: list[str] = Field(max_length=50)


class DraftView(BaseModel):
    """The article of a brief, if any, and its latest generation, if any."""

    article: ArticleView | None
    generation: GenerationView | None


ExportKind = Literal["pdf", "docx", "html", "md", "txt", "json"]


class SaveBody(BaseModel):
    """A version retouched in the editor (X03, ADR-0036)."""

    title: str = Field(max_length=1000)
    document: dict[str, Any]  # « Document plateforme v1 », checked by the server
    updated_at: datetime  # of the version as the editor loaded it
    as_new: bool = False  # « Enregistrer comme nouvelle version »


def _refused(error: BriefError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.code)


def build_router(
    briefs: Briefs,
    drafts: Drafts,
    editing: Editing,
    exports: Exports,
    library: Library,
    workspace_context: Callable[..., WorkspaceContext],
) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(prefix=PREFIX + "/{workspace_id}", dependencies=[Depends(same_origin)])

    @router.get("/brief-vocabulary")
    def brief_vocabulary(context: Context) -> VocabularyView:
        """The same for every workspace in phase 1; each workspace edits its own in phase 2."""
        lists = {
            field: [
                ChoiceView(
                    key=c.key,
                    label=c.label,
                    definition=c.definition,
                    length_max=None if c.length_max is None else c.length_max.value,
                )
                for c in values
            ]
            for field, values in VOCABULARY.items()
        }
        return VocabularyView(
            **lists,
            tone_default=TONE_DEFAULT,
            length_words={length.value: words for length, words in WORDS.items()},
            matter_share=MATTER_SHARE,
            matter_floor=MATTER_FLOOR,
        )

    @router.get("/briefs")
    def list_briefs(context: Context) -> list[BriefView]:
        """The briefs of the workspace, the most recently changed first."""
        return [BriefView.of(brief) for brief in briefs.list(context)]

    @router.post("/briefs", status_code=status.HTTP_201_CREATED)
    def create_brief(body: BriefBody, context: Context) -> BriefView:
        """Creates a brief; its items move to drafting in the triage of its author."""
        try:
            return BriefView.of(briefs.create(context, body.fields()))
        except BriefError as error:
            raise _refused(error) from error

    @router.get("/briefs/{brief_id}")
    def get_brief(brief_id: UUID, context: Context) -> BriefView:
        brief = briefs.get(context, brief_id)
        if brief is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brief_not_found")
        return BriefView.of(brief)

    @router.put("/briefs/{brief_id}")
    def update_brief(brief_id: UUID, body: BriefBody, context: Context) -> BriefView:
        try:
            brief = briefs.update(context, brief_id, body.fields())
        except BriefError as error:
            raise _refused(error) from error
        if brief is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brief_not_found")
        return BriefView.of(brief)

    @router.delete("/briefs/{brief_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_brief(brief_id: UUID, context: Context) -> None:
        if not briefs.delete(context, brief_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brief_not_found")

    @router.get("/briefs/{brief_id}/sources")
    def brief_sources(brief_id: UUID, context: Context) -> list[SourceTextView]:
        """The texts of the brief's sources, for the reference panel of « Comparer »."""
        texts = drafts.sources(context, brief_id)
        if texts is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brief_not_found")
        return [
            SourceTextView(
                key=f"S{number}",
                title=text.title,
                url=text.url,
                publisher=text.publisher,
                published_at=text.published_at,
                words=len(text.text.split()),
                text=text.text,
            )
            for number, text in enumerate(texts, start=1)
        ]

    @router.get("/briefs/{brief_id}/draft")
    def get_draft(brief_id: UUID, context: Context) -> DraftView:
        """The article written from the brief, with its versions, and the latest generation."""
        if briefs.get(context, brief_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brief_not_found")
        article = drafts.article(context, brief_id)
        generation = drafts.latest_generation(context, brief_id)
        return DraftView(
            article=None if article is None else ArticleView.of(article),
            generation=None if generation is None else GenerationView.of(generation),
        )

    @router.delete("/briefs/{brief_id}/details", status_code=status.HTTP_204_NO_CONTENT)
    def clear_details(brief_id: UUID, context: Context) -> None:
        """Empties the details and attempts of the drafts of the brief (diagnostics only: the
        versions themselves stay)."""
        if drafts.clear_details(context, brief_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brief_not_found")

    @router.post("/briefs/{brief_id}/generations", status_code=status.HTTP_202_ACCEPTED)
    def generate(
        brief_id: UUID, context: Context, body: GenerateBody | None = None
    ) -> GenerationView:
        """Asks the worker for a draft of the brief, a new version of its article; while one
        runs, the same is answered. Sources too thin: 409 `insufficient_matter`, unless the
        author confirms (« Générer quand même »)."""
        try:
            generation = drafts.start(context, brief_id, force=body is not None and body.force)
        except MatterError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, "insufficient_matter") from error
        if generation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brief_not_found")
        return GenerationView.of(generation)

    @router.delete("/briefs/{brief_id}/generations/running")
    def cancel_generation(brief_id: UUID, context: Context) -> GenerationView:
        """Cancels the draft being written for the brief: no version is made from it."""
        cancelled = drafts.cancel(context, brief_id)
        if cancelled is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no_running_generation")
        return GenerationView.of(cancelled)

    @router.get(
        "/articles/{article_id}/versions/{number}/export/{kind}",
        response_class=Response,
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    def export_version(
        article_id: UUID, number: int, kind: ExportKind, context: Context
    ) -> Response:
        """A version as a file (X03c): pdf, docx, html, md (a ZIP when it has images), txt or json,
        with its Sources block and AI mention. Made on demand, never stored."""
        exported = exports.export(context, article_id, number, kind)
        if exported is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "version_not_found")
        return Response(
            exported.data,
            media_type=exported.mime,
            headers={
                "Content-Disposition": f'attachment; filename="{exported.filename}"',
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    @router.get("/library")
    def list_library(
        context: Context,
        q: str = "",
        status: Literal["brouillon", "valide", "archive"] | None = None,
        tag: str | None = None,
    ) -> list[LibraryEntryView]:
        """The Library (X04): the articles sent to it, the latest changed first; `q` searches the
        title and the text of the latest version; archived articles only with status=archive."""
        return [LibraryEntryView.of(e) for e in library.entries(context, q, status, tag)]

    @router.get("/library/tags")
    def list_tags(context: Context) -> list[str]:
        return library.tags(context)

    @router.get("/articles/{article_id}")
    def get_article(article_id: UUID, context: Context) -> ArticleView:
        article = library.article(context, article_id)
        if article is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "article_not_found")
        return ArticleView.of(article)

    @router.post("/articles/{article_id}/send")
    def send_article(article_id: UUID, body: SendBody, context: Context) -> ArticleView:
        """« Envoyer en Bibliothèque », then « Valider » a later version: the version given is the
        one exports and publications take."""
        article = library.send(context, article_id, body.number)
        if article is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "version_not_found")
        return ArticleView.of(article)

    @router.post("/articles/{article_id}/archive")
    def archive_article(article_id: UUID, body: ArchiveBody, context: Context) -> ArticleView:
        article = library.archive(context, article_id, body.archived)
        if article is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "article_not_found")
        return ArticleView.of(article)

    @router.put("/articles/{article_id}/tags")
    def set_tags(article_id: UUID, body: TagsBody, context: Context) -> ArticleView:
        try:
            article = library.set_tags(context, article_id, body.tags)
        except TagError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_tags") from error
        if article is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "article_not_found")
        return ArticleView.of(article)

    @router.get("/generations/{generation_id}")
    def get_generation(generation_id: UUID, context: Context) -> GenerationView:
        generation = drafts.generation(context, generation_id)
        if generation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "generation_not_found")
        return GenerationView.of(generation)

    @router.put("/articles/{article_id}/versions/{number}")
    def save_version(
        article_id: UUID, number: int, body: SaveBody, context: Context
    ) -> VersionView:
        """« Enregistrer » a version retouched in the editor: a person's version is updated, a
        version of the model is kept and the person's version is added. With `as_new`, a new
        version is added whatever the version edited. 409 when the version changed since the
        editor loaded it."""
        saved = editing.save(
            context, article_id, number, body.title, body.document, body.updated_at, body.as_new
        )
        if saved.refusal == "not_found":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "version_not_found")
        if saved.refusal == "conflict":
            raise HTTPException(status.HTTP_409_CONFLICT, "version_changed")
        if saved.version is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_document")
        return VersionView.of(saved.version)

    @router.delete(
        "/articles/{article_id}/versions/{number}", status_code=status.HTTP_204_NO_CONTENT
    )
    def discard_version(article_id: UUID, number: int, context: Context) -> None:
        """Removes the copy « Modifier » made of a model's version when the editor is closed
        without a change. 409 for any version saved since, or written by the model."""
        if not editing.discard(context, article_id, number):
            raise HTTPException(status.HTTP_409_CONFLICT, "version_kept")

    return router
