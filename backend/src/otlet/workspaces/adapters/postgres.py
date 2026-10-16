# SPDX-License-Identifier: AGPL-3.0-or-later
"""The workspace store on PostgreSQL. Every query carries the user context, and the workspace
context when there is one: row-level security filters what the queries forget (ADR-0028)."""

from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.platform.database import scoped_transaction
from otlet.workspaces.domain.model import Role, Workspace


class PostgresWorkspaceStore:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def list_for(self, user_id: UUID) -> list[Workspace]:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT w.id, w.name, m.role FROM workspaces AS w"
                    " JOIN workspace_members AS m ON m.workspace_id = w.id"
                    " WHERE m.user_id = :user ORDER BY w.name, w.id"
                ),
                {"user": user_id},
            ).all()
        return [Workspace(id=row.id, name=row.name, role=Role(row.role)) for row in rows]

    def create(self, user_id: UUID, name: str) -> Workspace:
        workspace_id = uuid4()
        with scoped_transaction(
            self._engine, workspace_id=workspace_id, user_id=user_id
        ) as connection:
            connection.execute(
                sa.text("INSERT INTO workspaces (id, name) VALUES (:id, :name)"),
                {"id": workspace_id, "name": name},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO workspace_members (workspace_id, user_id, role)"
                    " VALUES (:workspace, :user, :role)"
                ),
                {"workspace": workspace_id, "user": user_id, "role": Role.OWNER.value},
            )
        return Workspace(id=workspace_id, name=name, role=Role.OWNER)

    def role_of(self, user_id: UUID, workspace_id: UUID) -> Role | None:
        with scoped_transaction(
            self._engine, workspace_id=workspace_id, user_id=user_id
        ) as connection:
            role = connection.execute(
                sa.text(
                    "SELECT role FROM workspace_members"
                    " WHERE workspace_id = :workspace AND user_id = :user"
                ),
                {"workspace": workspace_id, "user": user_id},
            ).scalar_one_or_none()
        return None if role is None else Role(role)
