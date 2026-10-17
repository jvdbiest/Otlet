# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the briefs (U03, F-RED-01), under a workspace (F03)."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.application.briefs import Briefs
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


def _refused(error: BriefError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.code)


def build_router(briefs: Briefs, workspace_context: Callable[..., WorkspaceContext]) -> APIRouter:
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

    return router
