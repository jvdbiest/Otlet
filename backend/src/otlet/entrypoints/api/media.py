# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the images of a workspace (X03b): imported from the editor, read back by it. The
médiathèque (ADR-0040): the images listed in two views, described, kept in the bank of images,
deleted while no article shows them."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.media.application.library import MediaLibrary
from otlet.media.domain.media import (
    FORMATS,
    MAX_BYTES,
    Description,
    Entry,
    Media,
    MediaError,
    Outcome,
    Usage,
    file_name,
)
from otlet.workspaces.domain.model import WorkspaceContext


class MediaView(BaseModel):
    id: UUID
    mime: str
    width: int
    height: int
    size: int
    created_at: datetime
    name: str | None
    description: str | None
    origin: Literal["editor", "library", "source", "generated"]
    in_bank: bool
    credit: str | None
    licence: str | None
    source_url: str | None
    tags: list[str]

    @classmethod
    def of(cls, media: Media) -> "MediaView":
        return cls(
            id=media.id,
            mime=media.mime,
            width=media.width,
            height=media.height,
            size=media.size,
            created_at=media.created_at,
            name=media.name,
            description=media.description,
            origin=cast(Any, media.origin),
            in_bank=media.in_bank,
            credit=media.credit,
            licence=media.licence,
            source_url=media.source_url,
            tags=list(media.tags),
        )


class MediaEntryView(MediaView):
    articles: int  # the number of articles that show it

    @classmethod
    def of_entry(cls, entry: Entry) -> "MediaEntryView":
        return cls(**MediaView.of(entry.media).model_dump(), articles=entry.articles)


class UsageView(BaseModel):
    article_id: UUID
    title: str
    status: str
    versions: list[int]

    @classmethod
    def of(cls, usage: Usage) -> "UsageView":
        return cls(
            article_id=usage.article_id,
            title=usage.title,
            status=usage.status,
            versions=list(usage.versions),
        )


class MediaDetailsView(BaseModel):
    media: MediaView
    usages: list[UsageView]


class DescriptionBody(BaseModel):
    """What a person says of an image; an empty text clears it."""

    name: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=5000)
    credit: str | None = Field(default=None, max_length=2000)
    licence: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=4000)


class MediaTagsBody(BaseModel):
    tags: list[str] = Field(max_length=100)


class MediaSelectionBody(BaseModel):
    media_ids: list[UUID] = Field(min_length=1, max_length=200)


class BankSelectionBody(MediaSelectionBody):
    in_bank: bool


class MediaFailedView(BaseModel):
    media_id: UUID
    reason: Literal["media_not_found", "in_use"]


class MediaOutcomeView(BaseModel):
    done: list[UUID]
    failed: list[MediaFailedView]

    @classmethod
    def of(cls, outcome: Outcome) -> "MediaOutcomeView":
        return cls(
            done=list(outcome.done),
            failed=[
                MediaFailedView(media_id=i, reason=cast(Any, reason))
                for i, reason in outcome.failed
            ],
        )


# The body is the image itself, as the browser has it (no form): its type is checked by decoding
# it, never taken from the request.
UPLOAD = {
    "requestBody": {
        "required": True,
        "content": {
            mime: {"schema": {"type": "string", "format": "binary"}}
            for mime in (*FORMATS, "image/gif")
        },
    }
}
IMAGE_HEADERS = {
    "Cache-Control": "private, max-age=31536000, immutable",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Content-Disposition": "inline",
}


def build_router(
    library: MediaLibrary, workspace_context: Callable[..., WorkspaceContext]
) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(prefix=PREFIX + "/{workspace_id}", dependencies=[Depends(same_origin)])

    @router.post("/media", status_code=status.HTTP_201_CREATED, openapi_extra=UPLOAD)
    async def import_image(
        request: Request,
        context: Context,
        name: Annotated[str | None, Query(max_length=500)] = None,
        bank: bool = False,
    ) -> MediaView:
        """Imports an image into the workspace: decoded, re-encoded without its metadata (GPS
        position, camera, author), no larger than 4096 pixels a side. 413 above 15 MB; 422 when
        it is not a JPEG, PNG, WebP or GIF image. `name`: the file's; `bank`: imported into the
        bank of images of the médiathèque."""
        declared = int(request.headers.get("content-length") or 0)
        if declared > MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "too_large")
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "too_large")
        try:
            # Decoding takes the processor: off the event loop.
            media = await run_in_threadpool(library.import_image, context, bytes(data), name, bank)
        except MediaError as error:
            code = status.HTTP_413_CONTENT_TOO_LARGE if error.code == "too_large" else 422
            raise HTTPException(code, error.code) from error
        return MediaView.of(media)

    @router.get("/media")
    def list_media(
        context: Context,
        view: Literal["articles", "bank"] = "articles",
        q: Annotated[str, Query(max_length=200)] = "",
        used: bool | None = None,
        tag: Annotated[str | None, Query(max_length=100)] = None,
    ) -> list[MediaEntryView]:
        """The images of a view of the médiathèque, newest first: those of the articles, or
        those of the bank of images; `used` keeps those some article shows, or the others."""
        return [MediaEntryView.of_entry(e) for e in library.entries(context, view, q, used, tag)]

    @router.post(
        "/media/export",
        response_class=Response,
        responses={200: {"content": {"application/zip": {}}}},
    )
    def export_originals(body: MediaSelectionBody, context: Context) -> Response:
        """The files Otlet stores of the images chosen, in one ZIP, unchanged."""
        data = library.export_originals(context, body.media_ids)
        if data is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "media_not_found")
        return Response(
            data,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="images.zip"',
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    @router.get(
        "/media/{media_id}/original",
        response_class=Response,
        responses={200: {"content": {mime: {} for mime in FORMATS}}},
    )
    def download_original(media_id: UUID, context: Context) -> Response:
        """The file Otlet stores of an image, unchanged, to save: « Télécharger l'original »."""
        found = library.read(context, media_id)
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "media_not_found")
        media, data = found
        return Response(
            data,
            media_type=media.mime,
            headers={
                **IMAGE_HEADERS,
                "Content-Disposition": f'attachment; filename="{file_name(media)}"',
            },
        )

    @router.get("/media/tags")
    def media_tags(context: Context) -> list[str]:
        """The tags of the images of the workspace, in order."""
        return library.tags(context)

    @router.put("/media/{media_id}/tags")
    def set_media_tags(media_id: UUID, body: MediaTagsBody, context: Context) -> MediaView:
        """Tags an image (40 characters, 20 tags at most: 422 invalid_tags)."""
        try:
            media = library.set_tags(context, media_id, body.tags)
        except MediaError as error:
            raise HTTPException(422, error.code) from error
        if media is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "media_not_found")
        return MediaView.of(media)

    @router.post("/media/bank")
    def keep_selection(body: BankSelectionBody, context: Context) -> MediaOutcomeView:
        """Adds the images chosen to the bank of images, or takes them out of it."""
        return MediaOutcomeView.of(library.keep_many(context, body.media_ids, body.in_bank))

    @router.post("/media/delete")
    def delete_selection(body: MediaSelectionBody, context: Context) -> MediaOutcomeView:
        """Deletes the images chosen that no article shows, in any version; the others are
        refused (in_use)."""
        return MediaOutcomeView.of(library.delete_many(context, body.media_ids))

    @router.get("/media/{media_id}/details")
    def media_details(media_id: UUID, context: Context) -> MediaDetailsView:
        """An image, and the articles that show it, with their versions."""
        found = library.read_description(context, media_id)
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "media_not_found")
        return MediaDetailsView(
            media=MediaView.of(found),
            usages=[UsageView.of(u) for u in library.usages(context, media_id)],
        )

    @router.patch("/media/{media_id}")
    def describe_media(media_id: UUID, body: DescriptionBody, context: Context) -> MediaView:
        """Names, describes, credits an image. 422 too_long or invalid_url."""
        try:
            media = library.describe(
                context,
                media_id,
                Description(
                    body.name, body.description, body.credit, body.licence, body.source_url
                ),
            )
        except MediaError as error:
            raise HTTPException(422, error.code) from error
        if media is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "media_not_found")
        return MediaView.of(media)

    @router.get(
        "/media/{media_id}/thumbnail",
        response_class=Response,
        responses={200: {"content": {"image/webp": {}}}},
    )
    def read_thumbnail(media_id: UUID, context: Context) -> Response:
        """The small image the médiathèque shows, never the original."""
        data = library.thumbnail(context, media_id)
        if data is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "media_not_found")
        return Response(data, media_type="image/webp", headers=IMAGE_HEADERS)

    @router.get(
        "/media/{media_id}",
        response_class=Response,
        responses={200: {"content": {mime: {} for mime in FORMATS}}},
    )
    def read_image(media_id: UUID, context: Context) -> Response:
        """The file of an image of the workspace; never shown to anyone outside it."""
        found = library.read(context, media_id)
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "media_not_found")
        media, data = found
        return Response(data, media_type=media.mime, headers=IMAGE_HEADERS)

    return router
