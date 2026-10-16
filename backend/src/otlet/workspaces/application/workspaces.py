# SPDX-License-Identifier: AGPL-3.0-or-later
"""Listing, creating and entering workspaces. Entering one is the only way to obtain a
WorkspaceContext, which every workspace-scoped operation requires (F03)."""

from typing import Protocol
from uuid import UUID

from otlet.workspaces.domain import model
from otlet.workspaces.domain.model import Role, Workspace, WorkspaceContext


class WorkspaceStore(Protocol):
    def list_for(self, user_id: UUID) -> list[Workspace]: ...
    def create(self, user_id: UUID, name: str) -> Workspace: ...
    def role_of(self, user_id: UUID, workspace_id: UUID) -> Role | None: ...


class Workspaces:
    def __init__(self, store: WorkspaceStore) -> None:
        self._store = store

    def list_for(self, user_id: UUID) -> list[Workspace]:
        return self._store.list_for(user_id)

    def create(self, user_id: UUID, name: str) -> Workspace:
        """A new workspace, owned by its creator."""
        return self._store.create(user_id, model.check_name(name))

    def enter(self, user_id: UUID, workspace_id: UUID) -> WorkspaceContext | None:
        """The context of a member, or None: a workspace the user does not belong to is
        indistinguishable from one that does not exist."""
        role = self._store.role_of(user_id, workspace_id)
        if role is None:
            return None
        return WorkspaceContext(user_id=user_id, workspace_id=workspace_id, role=role)
