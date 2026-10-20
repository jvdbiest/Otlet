# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the images of a workspace (X03b): imported from the editor, read back by it."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.media.application.library import MediaLibrary
from otlet.media.domain.media import FORMATS, MAX_BYTES, Media, MediaError
from otlet.workspaces.domain.model import WorkspaceContext


class MediaView(BaseModel):
    id: UUID
    mime: str
    width: int
    height: int
    size: int
    created_at: datetime

    @classmethod
    def of(cls, media: Media) -> "MediaView":
        return cls(
            id=media.id,
            mime=media.mime,
            width=media.width,
            height=media.height,
            size=media.size,
            created_at=media.created_at,
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


def build_router(
    library: MediaLibrary, workspace_context: Callable[..., WorkspaceContext]
) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(prefix=PREFIX + "/{workspace_id}", dependencies=[Depends(same_origin)])

    @router.post("/media", status_code=status.HTTP_201_CREATED, openapi_extra=UPLOAD)
    async def import_image(request: Request, context: Context) -> MediaView:
        """Imports an image into the workspace: decoded, re-encoded without its metadata (GPS
        position, camera, author), no larger than 4096 pixels a side. 413 above 15 MB; 422 when
        it is not a JPEG, PNG, WebP or GIF image."""
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
            media = await run_in_threadpool(library.import_image, context, bytes(data))
        except MediaError as error:
            code = status.HTTP_413_CONTENT_TOO_LARGE if error.code == "too_large" else 422
            raise HTTPException(code, error.code) from error
        return MediaView.of(media)

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
        return Response(
            data,
            media_type=media.mime,
            headers={
                "Cache-Control": "private, max-age=31536000, immutable",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "Content-Disposition": "inline",
            },
        )

    return router
