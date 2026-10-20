# SPDX-License-Identifier: AGPL-3.0-or-later
"""The images of a workspace (X03b): imported, then read back by the editor and the renderer.
The médiathèque (ADR-0040): one image, two views (the images of the articles, the bank of
images), its description, where it is used, and its deletion while no article shows it."""

from collections.abc import Iterable, Sequence
from typing import Literal, Protocol
from uuid import UUID

from otlet.media.domain.media import (
    FORMATS,
    MAX_BYTES,
    NAME_MAX,
    THUMBNAIL_EXTENSION,
    Description,
    Entry,
    Image,
    Media,
    MediaError,
    Outcome,
    Usage,
    cleaned,
)
from otlet.workspaces.domain.model import WorkspaceContext

View = Literal["articles", "bank"]


class Images(Protocol):
    def normalize(self, data: bytes) -> Image:
        """The image decoded and re-encoded, or MediaError("not_an_image")."""
        ...

    def thumbnail(self, data: bytes) -> bytes:
        """A small WebP of a stored image, for the grid of the médiathèque."""
        ...


class Files(Protocol):
    def put(self, data: bytes, extension: str) -> str:
        """Stores the bytes under their SHA-256, once; that address."""
        ...

    def get(self, sha256: str, extension: str) -> bytes | None: ...


class MediaStore(Protocol):
    def add(
        self,
        workspace_id: UUID,
        user_id: UUID,
        sha256: str,
        image: Image,
        name: str | None = None,
        origin: str = "editor",
        thumbnail: str | None = None,
        in_bank: bool = False,
    ) -> Media: ...

    def get(self, workspace_id: UUID, media_id: UUID) -> Media | None: ...

    def existing(self, workspace_id: UUID, ids: list[UUID]) -> set[UUID]: ...

    def search(self, workspace_id: UUID, query: str) -> list[Media]: ...

    def describe(
        self, workspace_id: UUID, media_id: UUID, description: Description
    ) -> Media | None: ...

    def keep(self, workspace_id: UUID, media_id: UUID, in_bank: bool) -> bool: ...

    def set_thumbnail(self, workspace_id: UUID, media_id: UUID, sha256: str) -> None: ...

    def delete(self, workspace_id: UUID, media_id: UUID) -> bool: ...


class Usages(Protocol):
    """Where the images are shown: read in the articles, which the writing module keeps."""

    def media_counts(self, workspace_id: UUID) -> dict[UUID, int]:
        """For each image shown, the number of articles that show it."""
        ...

    def media_usages(
        self, workspace_id: UUID, media_id: UUID
    ) -> list[tuple[UUID, str, str, tuple[int, ...]]]:
        """The articles that show an image: id, title, status, and the versions."""
        ...


class NoUsages:
    def media_counts(self, workspace_id: UUID) -> dict[UUID, int]:
        return {}

    def media_usages(
        self, workspace_id: UUID, media_id: UUID
    ) -> list[tuple[UUID, str, str, tuple[int, ...]]]:
        return []


class MediaLibrary:
    def __init__(
        self, store: MediaStore, files: Files, images: Images, usages: Usages | None = None
    ) -> None:
        self._store = store
        self._files = files
        self._images = images
        self._usages = usages or NoUsages()

    def import_image(
        self,
        context: WorkspaceContext,
        data: bytes,
        name: str | None = None,
        bank: bool = False,
    ) -> Media:
        """An image sent by a person: refused when too large or not an image, stored once it
        is re-encoded, with its thumbnail. Never the bytes as they came. Imported into the
        bank of images, it is there at once."""
        if len(data) > MAX_BYTES:
            raise MediaError("too_large")
        if name is not None:
            name = " ".join(name.split())[:NAME_MAX] or None
        image = self._images.normalize(data)
        sha256 = self._files.put(image.data, FORMATS[image.mime])
        thumbnail = self._files.put(self._images.thumbnail(image.data), THUMBNAIL_EXTENSION)
        return self._store.add(
            context.workspace_id,
            context.user_id,
            sha256,
            image,
            name,
            "library" if bank else "editor",
            thumbnail,
            bank,
        )

    def read(self, context: WorkspaceContext, media_id: UUID) -> tuple[Media, bytes] | None:
        media = self._store.get(context.workspace_id, media_id)
        if media is None:
            return None
        data = self._files.get(media.sha256, FORMATS[media.mime])
        return None if data is None else (media, data)

    def read_description(self, context: WorkspaceContext, media_id: UUID) -> Media | None:
        return self._store.get(context.workspace_id, media_id)

    def thumbnail(self, context: WorkspaceContext, media_id: UUID) -> bytes | None:
        """The small image of the grid; made the first time for an image imported before."""
        media = self._store.get(context.workspace_id, media_id)
        if media is None:
            return None
        if media.thumbnail_sha256 is not None:
            found = self._files.get(media.thumbnail_sha256, THUMBNAIL_EXTENSION)
            if found is not None:
                return found
        original = self._files.get(media.sha256, FORMATS[media.mime])
        if original is None:
            return None
        data = self._images.thumbnail(original)
        sha256 = self._files.put(data, THUMBNAIL_EXTENSION)
        self._store.set_thumbnail(context.workspace_id, media_id, sha256)
        return data

    def existing(self, workspace_id: UUID, ids: Iterable[UUID]) -> set[UUID]:
        """Those of `ids` that are images of the workspace."""
        wanted = list(set(ids))
        return self._store.existing(workspace_id, wanted) if wanted else set()

    def entries(
        self,
        context: WorkspaceContext,
        view: View,
        query: str = "",
        used: bool | None = None,
    ) -> list[Entry]:
        """The images of a view, newest first: those of the articles (brought by the work on
        an article, or shown by one) or those of the bank. One image may be in both."""
        counts = self._usages.media_counts(context.workspace_id)
        found = []
        for media in self._store.search(context.workspace_id, " ".join(query.split())):
            articles = counts.get(media.id, 0)
            if view == "bank" and not media.in_bank:
                continue
            if view == "articles" and media.origin == "library" and articles == 0:
                continue
            if used is not None and used != (articles > 0):
                continue
            found.append(Entry(media, articles))
        return found

    def usages(self, context: WorkspaceContext, media_id: UUID) -> list[Usage]:
        return [
            Usage(article_id, title, status, versions)
            for article_id, title, status, versions in self._usages.media_usages(
                context.workspace_id, media_id
            )
        ]

    def describe(
        self, context: WorkspaceContext, media_id: UUID, description: Description
    ) -> Media | None:
        return self._store.describe(context.workspace_id, media_id, cleaned(description))

    def keep_many(
        self, context: WorkspaceContext, media_ids: Sequence[UUID], in_bank: bool
    ) -> Outcome:
        """Adds the images to the bank, or takes them out of it: they stay where they are."""
        done, failed = [], []
        for media_id in dict.fromkeys(media_ids):
            if self._store.keep(context.workspace_id, media_id, in_bank):
                done.append(media_id)
            else:
                failed.append((media_id, "media_not_found"))
        return Outcome(tuple(done), tuple(failed))

    def delete_many(self, context: WorkspaceContext, media_ids: Sequence[UUID]) -> Outcome:
        """Deletes the images no article shows, in any of its versions (Joël, 2026-10-20). The
        file stays until no workspace refers to it (ADR-0040)."""
        done, failed = [], []
        for media_id in dict.fromkeys(media_ids):
            if self._usages.media_usages(context.workspace_id, media_id):
                failed.append((media_id, "in_use"))
            elif self._store.delete(context.workspace_id, media_id):
                done.append(media_id)
            else:
                failed.append((media_id, "media_not_found"))
        return Outcome(tuple(done), tuple(failed))
