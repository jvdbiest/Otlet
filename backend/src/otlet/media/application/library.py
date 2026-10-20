# SPDX-License-Identifier: AGPL-3.0-or-later
"""The images of a workspace (X03b): imported, then read back by the editor and the renderer."""

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from otlet.media.domain.media import FORMATS, MAX_BYTES, Image, Media, MediaError
from otlet.workspaces.domain.model import WorkspaceContext


class Images(Protocol):
    def normalize(self, data: bytes) -> Image:
        """The image decoded and re-encoded, or MediaError("not_an_image")."""
        ...


class Files(Protocol):
    def put(self, data: bytes, extension: str) -> str:
        """Stores the bytes under their SHA-256, once; that address."""
        ...

    def get(self, sha256: str, extension: str) -> bytes | None: ...


class MediaStore(Protocol):
    def add(self, workspace_id: UUID, user_id: UUID, sha256: str, image: Image) -> Media: ...

    def get(self, workspace_id: UUID, media_id: UUID) -> Media | None: ...

    def existing(self, workspace_id: UUID, ids: list[UUID]) -> set[UUID]: ...


class MediaLibrary:
    def __init__(self, store: MediaStore, files: Files, images: Images) -> None:
        self._store = store
        self._files = files
        self._images = images

    def import_image(self, context: WorkspaceContext, data: bytes) -> Media:
        """An image sent by a person: refused when too large or not an image, stored once it
        is re-encoded. Never the bytes as they came."""
        if len(data) > MAX_BYTES:
            raise MediaError("too_large")
        image = self._images.normalize(data)
        sha256 = self._files.put(image.data, FORMATS[image.mime])
        return self._store.add(context.workspace_id, context.user_id, sha256, image)

    def read(self, context: WorkspaceContext, media_id: UUID) -> tuple[Media, bytes] | None:
        media = self._store.get(context.workspace_id, media_id)
        if media is None:
            return None
        data = self._files.get(media.sha256, FORMATS[media.mime])
        return None if data is None else (media, data)

    def existing(self, workspace_id: UUID, ids: Iterable[UUID]) -> set[UUID]:
        """Those of `ids` that are images of the workspace."""
        wanted = list(set(ids))
        return self._store.existing(workspace_id, wanted) if wanted else set()
