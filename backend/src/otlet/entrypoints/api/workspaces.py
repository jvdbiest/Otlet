# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workspace routes, and the dependencies that give every workspace-scoped route its context
(F03, ARCHITECTURE §8.1).

Every route under /api/workspaces/{workspace_id} depends on `workspace_context`: it answers 404
when the user is not a member, exactly as when the workspace does not exist. Routes that touch
the database take `WorkspaceConnection`, a transaction where row-level security shows the rows
of that workspace only. tests/entrypoints/test_api_isolation.py checks both rules on every
route of the application.
"""

from collections.abc import Callable, Iterator
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from otlet.entrypoints.api.auth import same_origin
from otlet.identity.domain.model import Session
from otlet.platform.database import scoped_transaction
from otlet.workspaces.application.workspaces import Workspaces
from otlet.workspaces.domain.model import (
    NAME_MAX_LENGTH,
    Workspace,
    WorkspaceContext,
    WorkspaceError,
)

PREFIX = "/api/workspaces"


class WorkspaceView(BaseModel):
    id: str
    name: str
    role: str

    @classmethod
    def of(cls, workspace: Workspace) -> "WorkspaceView":
        return cls(id=str(workspace.id), name=workspace.name, role=workspace.role.value)


class NewWorkspace(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)


def build_router(
    workspaces: Workspaces,
    engine: sa.Engine,
    current_session: Callable[..., Session],
) -> tuple[APIRouter, Callable[..., WorkspaceContext]]:
    CurrentSession = Annotated[Session, Depends(current_session)]

    def workspace_context(workspace_id: UUID, session: CurrentSession) -> WorkspaceContext:
        context = workspaces.enter(session.user_id, workspace_id)
        if context is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace_not_found")
        return context

    Context = Annotated[WorkspaceContext, Depends(workspace_context)]

    def workspace_connection(context: Context) -> Iterator[sa.Connection]:
        with scoped_transaction(
            engine, workspace_id=context.workspace_id, user_id=context.user_id
        ) as connection:
            yield connection

    WorkspaceConnection = Annotated[sa.Connection, Depends(workspace_connection)]
    router = APIRouter(prefix=PREFIX, dependencies=[Depends(same_origin)])

    @router.get("")
    def list_workspaces(session: CurrentSession) -> list[WorkspaceView]:
        return [WorkspaceView.of(workspace) for workspace in workspaces.list_for(session.user_id)]

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_workspace(body: NewWorkspace, session: CurrentSession) -> WorkspaceView:
        try:
            return WorkspaceView.of(workspaces.create(session.user_id, body.name))
        except WorkspaceError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    @router.get("/{workspace_id}")
    def get_workspace(context: Context, connection: WorkspaceConnection) -> WorkspaceView:
        name = connection.execute(
            sa.text("SELECT name FROM workspaces WHERE id = :id"), {"id": context.workspace_id}
        ).scalar_one()
        return WorkspaceView(id=str(context.workspace_id), name=name, role=context.role.value)

    return router, workspace_context
