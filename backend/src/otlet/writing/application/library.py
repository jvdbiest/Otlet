# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Library (X04, ADR-0037): the validated articles of a workspace. The brief is the workshop;
« Envoyer en Bibliothèque » validates a version and sends its article here. One brief, one
article, several versions."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.domain.article import Article, LibraryEntry

STATUSES = ("brouillon", "valide", "archive")
TAGS_MAX = 20
TAG_MAX = 40


class LibraryStore(Protocol):
    def article(self, workspace_id: UUID, article_id: UUID) -> Article | None: ...

    def send(self, workspace_id: UUID, article_id: UUID, number: int) -> bool:
        """Validates the version and sends the article; False when either does not exist."""
        ...

    def archive(self, workspace_id: UUID, article_id: UUID, archived: bool) -> bool: ...

    def set_tags(self, workspace_id: UUID, article_id: UUID, tags: Sequence[str]) -> bool: ...

    def library(
        self, workspace_id: UUID, query: str, status: str | None, tag: str | None
    ) -> list[LibraryEntry]: ...

    def tags(self, workspace_id: UUID) -> list[str]: ...


class TagError(ValueError):
    pass


def clean_tags(tags: Sequence[str]) -> list[str]:
    """Tags as kept: spaces folded, no empty one, no duplicate (whatever the case), in order."""
    kept: list[str] = []
    for tag in tags:
        tag = " ".join(tag.split())
        if not tag:
            continue
        if len(tag) > TAG_MAX:
            raise TagError(f"a tag has {TAG_MAX} characters at most")
        if tag.casefold() not in {k.casefold() for k in kept}:
            kept.append(tag)
    if len(kept) > TAGS_MAX:
        raise TagError(f"{TAGS_MAX} tags at most")
    return kept


class Library:
    def __init__(self, store: LibraryStore) -> None:
        self._store = store

    def article(self, context: WorkspaceContext, article_id: UUID) -> Article | None:
        return self._store.article(context.workspace_id, article_id)

    def send(self, context: WorkspaceContext, article_id: UUID, number: int) -> Article | None:
        """« Envoyer en Bibliothèque », and later « Valider » another version: the version given
        becomes the one exports and publications take."""
        if not self._store.send(context.workspace_id, article_id, number):
            return None
        return self._store.article(context.workspace_id, article_id)

    def archive(
        self, context: WorkspaceContext, article_id: UUID, archived: bool
    ) -> Article | None:
        if not self._store.archive(context.workspace_id, article_id, archived):
            return None
        return self._store.article(context.workspace_id, article_id)

    def set_tags(
        self, context: WorkspaceContext, article_id: UUID, tags: Sequence[str]
    ) -> Article | None:
        if not self._store.set_tags(context.workspace_id, article_id, clean_tags(tags)):
            return None
        return self._store.article(context.workspace_id, article_id)

    def entries(
        self,
        context: WorkspaceContext,
        query: str = "",
        status: str | None = None,
        tag: str | None = None,
    ) -> list[LibraryEntry]:
        if status is not None and status not in STATUSES:
            status = None
        return self._store.library(context.workspace_id, query[:200], status, tag or None)

    def tags(self, context: WorkspaceContext) -> list[str]:
        return self._store.tags(context.workspace_id)
