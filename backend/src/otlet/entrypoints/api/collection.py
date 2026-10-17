# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the sources and of the items they bring (U01). All live under a workspace and
depend on its context (F03); errors carry the stable code of CollectionError as `detail`."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from otlet.collection.application.collection import Collection
from otlet.collection.domain import model
from otlet.collection.domain.model import Check, CollectionError, Item, Source
from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.workspaces.domain.model import WorkspaceContext


class SourceView(BaseModel):
    id: str
    name: str
    url: str
    feed_url: str
    site_url: str | None
    interval_minutes: int
    active: bool
    legal_status: str
    legal_reason: str | None
    health: str
    created_at: datetime
    last_fetched_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    next_fetch_at: datetime | None
    item_count: int

    @classmethod
    def of(cls, source: Source) -> "SourceView":
        return cls(
            id=str(source.id),
            name=source.name,
            url=source.url,
            feed_url=source.feed_url,
            site_url=source.site_url,
            interval_minutes=source.interval_minutes,
            active=source.active,
            legal_status=source.legal_status.value,
            legal_reason=source.legal_reason,
            health=source.health.value,
            created_at=source.created_at,
            last_fetched_at=source.last_fetched_at,
            last_success_at=source.last_success_at,
            last_error=source.last_error,
            consecutive_failures=source.consecutive_failures,
            next_fetch_at=source.next_fetch_at,
            item_count=source.item_count,
        )


class CheckView(BaseModel):
    checked_at: datetime
    url: str
    allowed: bool
    reason: str
    detail: str

    @classmethod
    def of(cls, check: Check) -> "CheckView":
        return cls(
            checked_at=check.checked_at,
            url=check.url,
            allowed=check.allowed,
            reason=check.reason,
            detail=check.detail,
        )


class ItemView(BaseModel):
    id: str
    source_id: str | None
    source_name: str | None
    origin: str
    url: str | None
    title: str
    author: str | None
    published_at: datetime | None
    collected_at: datetime
    summary: str | None
    text: str | None
    text_status: str
    text_reason: str | None
    declared_origin: str | None
    usage_right: str | None
    duplicates: int

    @classmethod
    def of(cls, item: Item, *, with_text: bool = True) -> "ItemView":
        return cls(
            id=str(item.id),
            source_id=None if item.source_id is None else str(item.source_id),
            source_name=item.source_name,
            origin=item.origin.value,
            url=item.url,
            title=item.title,
            author=item.author,
            published_at=item.published_at,
            collected_at=item.collected_at,
            summary=item.summary,
            text=item.text if with_text else None,
            text_status=item.text_status.value,
            text_reason=item.text_reason,
            declared_origin=item.declared_origin,
            usage_right=item.usage_right,
            duplicates=item.duplicates,
        )


class NewSource(BaseModel):
    url: str = Field(min_length=1, max_length=model.URL_MAX_LENGTH)
    name: str | None = Field(default=None, max_length=model.NAME_MAX_LENGTH)
    interval_minutes: int = Field(
        default=model.INTERVAL_DEFAULT_MINUTES,
        ge=model.INTERVAL_MIN_MINUTES,
        le=model.INTERVAL_MAX_MINUTES,
    )


class SourceChanges(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=model.NAME_MAX_LENGTH)
    interval_minutes: int | None = Field(
        default=None, ge=model.INTERVAL_MIN_MINUTES, le=model.INTERVAL_MAX_MINUTES
    )
    active: bool | None = None


class ManualUrl(BaseModel):
    url: str = Field(min_length=1, max_length=model.URL_MAX_LENGTH)


class ItemSelection(BaseModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=200)


class RemovedView(BaseModel):
    removed: int


class ManualText(BaseModel):
    title: str = Field(min_length=1, max_length=model.TITLE_MAX_LENGTH)
    text: str = Field(min_length=1, max_length=model.MANUAL_TEXT_MAX_LENGTH)
    url: str | None = Field(default=None, max_length=model.URL_MAX_LENGTH)
    declared_origin: str = Field(max_length=model.DECLARATION_MAX_LENGTH)
    usage_right: str = Field(max_length=model.DECLARATION_MAX_LENGTH)


def _refused(error: CollectionError) -> HTTPException:
    code = (
        status.HTTP_409_CONFLICT
        if error.code == "already_followed"
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return HTTPException(code, error.code)


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what}_not_found")


def build_router(
    collection: Collection, workspace_context: Callable[..., WorkspaceContext]
) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(prefix=PREFIX + "/{workspace_id}", dependencies=[Depends(same_origin)])

    @router.get("/sources")
    def list_sources(context: Context) -> list[SourceView]:
        return [SourceView.of(source) for source in collection.list_sources(context)]

    @router.post("/sources", status_code=status.HTTP_201_CREATED)
    def add_source(body: NewSource, context: Context) -> SourceView:
        try:
            source = collection.add_source(context, body.url, body.name, body.interval_minutes)
        except CollectionError as error:
            raise _refused(error) from error
        return SourceView.of(source)

    @router.get("/sources/{source_id}")
    def get_source(source_id: UUID, context: Context) -> SourceView:
        source = collection.get_source(context, source_id)
        if source is None:
            raise _not_found("source")
        return SourceView.of(source)

    @router.patch("/sources/{source_id}")
    def update_source(source_id: UUID, body: SourceChanges, context: Context) -> SourceView:
        try:
            source = collection.update_source(
                context,
                source_id,
                name=body.name,
                interval_minutes=body.interval_minutes,
                active=body.active,
            )
        except CollectionError as error:
            raise _refused(error) from error
        if source is None:
            raise _not_found("source")
        return SourceView.of(source)

    @router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_source(source_id: UUID, context: Context) -> None:
        if not collection.delete_source(context, source_id):
            raise _not_found("source")

    @router.post("/sources/{source_id}/collect", status_code=status.HTTP_202_ACCEPTED)
    def collect_now(source_id: UUID, context: Context) -> None:
        """Collects the source as soon as a worker is free, without waiting for its turn."""
        if not collection.collect_now(context, source_id):
            raise _not_found("source")

    @router.get("/sources/{source_id}/checks")
    def list_checks(source_id: UUID, context: Context) -> list[CheckView]:
        """The compliance journal of the source (CJ-03), newest first."""
        if collection.get_source(context, source_id) is None:
            raise _not_found("source")
        return [CheckView.of(check) for check in collection.checks(context, source_id)]

    @router.get("/items")
    def list_items(
        context: Context,
        source_id: UUID | None = None,
        before: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[ItemView]:
        """The latest items, newest first, without their full text; `before` (the id of the
        last item of the previous page) pages back."""
        items = collection.list_items(context, source_id=source_id, before=before, limit=limit)
        return [ItemView.of(item, with_text=False) for item in items]

    @router.get("/items/{item_id}")
    def get_item(item_id: UUID, context: Context) -> ItemView:
        item = collection.get_item(context, item_id)
        if item is None:
            raise _not_found("item")
        return ItemView.of(item)

    @router.post("/items/manual-url", status_code=status.HTTP_201_CREATED)
    def add_manual_url(body: ManualUrl, context: Context) -> ItemView:
        try:
            return ItemView.of(collection.add_manual_url(context, body.url))
        except CollectionError as error:
            raise _refused(error) from error

    @router.post("/items/manual-text", status_code=status.HTTP_201_CREATED)
    def add_manual_text(body: ManualText, context: Context) -> ItemView:
        try:
            item = collection.add_manual_text(
                context,
                title=body.title,
                text=body.text,
                url=body.url,
                declared_origin=body.declared_origin,
                usage_right=body.usage_right,
            )
        except CollectionError as error:
            raise _refused(error) from error
        return ItemView.of(item)

    @router.post("/items/remove")
    def remove_items(body: ItemSelection, context: Context) -> RemovedView:
        """Removes items from the watch of the whole workspace, with their text. An item of a
        feed leaves its address behind, so that the collection does not bring it back."""
        return RemovedView(removed=collection.remove_items(context, body.item_ids))

    return router
