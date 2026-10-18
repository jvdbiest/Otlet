# SPDX-License-Identifier: AGPL-3.0-or-later
"""A version retouched in the editor (X03, ADR-0036): « Enregistrer » updates a person's version;
« Enregistrer comme nouvelle version » adds one. A version written by a model never changes:
saving it adds the person's version, once."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.domain.article import Version
from otlet.writing.domain.document import check, with_origins

TITLE_MAX = 300


class VersionStore(Protocol):
    def version(self, workspace_id: UUID, article_id: UUID, number: int) -> Version | None: ...

    def update_version(
        self,
        workspace_id: UUID,
        article_id: UUID,
        number: int,
        title: str,
        document: dict[str, Any],
        updated_at: datetime,
    ) -> Version | None:
        """Saves over a person's version if it was not changed since `updated_at`; None if it
        was (another tab saved first)."""
        ...

    def add_person_version(
        self,
        workspace_id: UUID,
        user_id: UUID,
        article_id: UUID,
        based_on: int,
        title: str,
        document: dict[str, Any],
    ) -> Version: ...

    def discard_untouched(self, workspace_id: UUID, article_id: UUID, number: int) -> bool:
        """Removes a person's version never saved since it was made; False for any other."""
        ...


@dataclass(frozen=True, slots=True)
class Saved:
    """The version saved, or why there is none: not_found, conflict, or the errors of the
    document."""

    version: Version | None = None
    refusal: str | None = None
    errors: tuple[str, ...] = ()


class Editing:
    def __init__(self, versions: VersionStore) -> None:
        self._versions = versions

    def save(
        self,
        context: WorkspaceContext,
        article_id: UUID,
        number: int,
        title: str,
        document: Any,
        updated_at: datetime,
        as_new: bool,
    ) -> Saved:
        edited = self._versions.version(context.workspace_id, article_id, number)
        if edited is None:
            return Saved(refusal="not_found")
        title = " ".join(title.split())
        sources = list(edited.document["attrs"]["sources"])
        errors = check(document, {s["id"] for s in sources})
        if not title or len(title) > TITLE_MAX:
            errors.insert(0, f"title: 1 to {TITLE_MAX} characters")
        if errors:
            return Saved(refusal="invalid", errors=tuple(errors))
        saved = with_origins(document, edited.document, sources)
        if as_new or edited.origin == "ia":
            made = self._versions.add_person_version(
                context.workspace_id, context.user_id, article_id, number, title, saved
            )
            return Saved(version=made)
        if edited.updated_at is not None and edited.updated_at != updated_at:
            return Saved(refusal="conflict")
        updated = self._versions.update_version(
            context.workspace_id, article_id, number, title, saved, updated_at
        )
        return Saved(version=updated) if updated is not None else Saved(refusal="conflict")

    def discard(self, context: WorkspaceContext, article_id: UUID, number: int) -> bool:
        """The copy of a model's version that « Modifier » made, closed without a change (Joël,
        2026-10-18): it goes, so that opening the editor leaves no version behind. Only a
        person's version never saved since it was made can go."""
        return self._versions.discard_untouched(context.workspace_id, article_id, number)
