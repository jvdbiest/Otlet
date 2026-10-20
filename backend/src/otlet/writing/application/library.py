# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Library (X04, ADR-0037): the validated articles of a workspace. The brief is the workshop;
« Envoyer en Bibliothèque » validates a version and sends its article here. One brief, one
article, several versions."""

from collections.abc import Sequence
from typing import Any, Protocol
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

    def create_article(
        self,
        workspace_id: UUID,
        user_id: UUID,
        title: str,
        document: dict[str, Any],
        tags: Sequence[str] = (),
    ) -> UUID: ...

    def set_tags(self, workspace_id: UUID, article_id: UUID, tags: Sequence[str]) -> bool: ...

    def library(
        self,
        workspace_id: UUID,
        query: str,
        status: str | None,
        tag: str | None,
        topic_id: UUID | None = None,
    ) -> list[LibraryEntry]: ...

    def tags(self, workspace_id: UUID) -> list[str]: ...

    def library_topics(self, workspace_id: UUID) -> list[tuple[UUID, str]]: ...


class TagError(ValueError):
    pass


class TitleError(ValueError):
    pass


TITLE_MAX = 200


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

    def create(self, context: WorkspaceContext, title: str) -> Article:
        """An article written by hand, without a brief (Joël, 2026-10-20): in the Library at
        once, as a draft, its first version an empty page."""
        title = " ".join(title.split())
        if not 1 <= len(title) <= TITLE_MAX:
            raise TitleError(f"a title has 1 to {TITLE_MAX} characters")
        document = {
            "type": "doc",
            "attrs": {"version_schema": 1, "langue": "fr", "sources": []},
            "content": [{"type": "paragraph", "attrs": {"id": "b1", "origine": "humain"}}],
        }
        made = self._store.create_article(context.workspace_id, context.user_id, title, document)
        article = self._store.article(context.workspace_id, made)
        if article is None:  # just written, in the same workspace
            raise RuntimeError("the article just written is missing")
        return article

    def duplicate(self, context: WorkspaceContext, article_id: UUID, number: int) -> Article | None:
        """« Dupliquer » (Joël, 2026-10-20): a new article, without a brief, whose first version
        is a copy of the version given, with its sources and images; its tags follow. None when
        the article or the version does not exist."""
        source = self._store.article(context.workspace_id, article_id)
        version = (
            None
            if source is None
            else next((v for v in source.versions if v.number == number), None)
        )
        if source is None or version is None:
            return None
        title = f"Copie de {version.title}"[:TITLE_MAX]
        made = self._store.create_article(
            context.workspace_id, context.user_id, title, version.document, source.tags
        )
        return self._store.article(context.workspace_id, made)

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
        topic_id: UUID | None = None,
    ) -> list[LibraryEntry]:
        if status is not None and status not in STATUSES:
            status = None
        return self._store.library(context.workspace_id, query[:200], status, tag or None, topic_id)

    def tags(self, context: WorkspaceContext) -> list[str]:
        return self._store.tags(context.workspace_id)

    def topics(self, context: WorkspaceContext) -> list[tuple[UUID, str]]:
        """The topics of the articles of the Library: those of the items of their briefs."""
        return self._store.library_topics(context.workspace_id)
