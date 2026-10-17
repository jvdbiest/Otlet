# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the briefs (U03, F-RED-01), under a workspace (F03)."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.application.briefs import Briefs
from otlet.writing.application.drafts import Drafts
from otlet.writing.domain.article import Article, Generation, Version
from otlet.writing.domain.brief import (
    ITEMS_MAX,
    Brief,
    BriefError,
    BriefFields,
    BriefItem,
    Length,
    ModelChoice,
)


class BriefItemView(BaseModel):
    id: UUID
    title: str
    url: str | None
    source_id: UUID | None
    source_name: str | None
    published_at: datetime | None

    @classmethod
    def of(cls, item: BriefItem) -> "BriefItemView":
        return cls(
            id=item.id,
            title=item.title,
            url=item.url,
            source_id=item.source_id,
            source_name=item.source_name,
            published_at=item.published_at,
        )


class BriefView(BaseModel):
    id: UUID
    title: str
    angle: str
    audience: str
    tone: str
    length: Literal["short", "medium", "long"]
    language: str
    channel: str
    provider_id: UUID | None  # None: the profile of the author
    model: str | None
    items: list[BriefItemView]
    sources: int
    single_source: bool  # fewer than two sources: said, not refused
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, brief: Brief) -> "BriefView":
        fields = brief.fields
        return cls(
            id=brief.id,
            title=fields.title,
            angle=fields.angle,
            audience=fields.audience,
            tone=fields.tone,
            length=fields.length.value,
            language=fields.language,
            channel=fields.channel,
            provider_id=None if fields.model is None else fields.model.provider_id,
            model=None if fields.model is None else fields.model.model,
            items=[BriefItemView.of(item) for item in brief.items],
            sources=brief.sources,
            single_source=brief.single_source,
            created_at=brief.created_at,
            updated_at=brief.updated_at,
        )


class BriefBody(BaseModel):
    title: str
    item_ids: list[UUID] = Field(min_length=1, max_length=ITEMS_MAX)
    angle: str = ""
    audience: str = ""
    tone: str = ""
    length: Literal["short", "medium", "long"] = "medium"
    language: str = "fr"
    channel: str = ""
    provider_id: UUID | None = None  # with `model`; none for the profile of the author
    model: str | None = None

    def fields(self) -> BriefFields:
        return BriefFields(
            title=self.title,
            item_ids=tuple(self.item_ids),
            angle=self.angle,
            audience=self.audience,
            tone=self.tone,
            length=Length(self.length),
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
    created_at: datetime

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
            created_at=version.created_at,
        )


class ArticleView(BaseModel):
    id: UUID
    title: str
    versions: list[VersionView]  # the latest last

    @classmethod
    def of(cls, article: Article) -> "ArticleView":
        return cls(
            id=article.id,
            title=article.title,
            versions=[VersionView.of(v) for v in article.versions],
        )


class DraftView(BaseModel):
    """The article of a brief, if any, and its latest generation, if any."""

    article: ArticleView | None
    generation: GenerationView | None


def _refused(error: BriefError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.code)


def build_router(
    briefs: Briefs, drafts: Drafts, workspace_context: Callable[..., WorkspaceContext]
) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(prefix=PREFIX + "/{workspace_id}", dependencies=[Depends(same_origin)])

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

    @router.post("/briefs/{brief_id}/generations", status_code=status.HTTP_202_ACCEPTED)
    def generate(brief_id: UUID, context: Context) -> GenerationView:
        """Asks the worker for a draft of the brief, a new version of its article; while one
        runs, the same is answered."""
        generation = drafts.start(context, brief_id)
        if generation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brief_not_found")
        return GenerationView.of(generation)

    @router.get("/generations/{generation_id}")
    def get_generation(generation_id: UUID, context: Context) -> GenerationView:
        generation = drafts.generation(context, generation_id)
        if generation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "generation_not_found")
        return GenerationView.of(generation)

    return router
