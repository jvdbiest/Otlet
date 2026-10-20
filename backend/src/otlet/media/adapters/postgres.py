# SPDX-License-Identifier: AGPL-3.0-or-later
"""The description of the images of each workspace, on PostgreSQL."""

from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.media.domain.media import Image, Media
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here

COLUMNS = "id, sha256, mime, width, height, size, created_at"


def _media(row: sa.Row[Any]) -> Media:
    return Media(
        id=row.id,
        sha256=row.sha256,
        mime=row.mime,
        width=row.width,
        height=row.height,
        size=row.size,
        created_at=row.created_at,
    )


class PostgresMediaStore:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def add(self, workspace_id: UUID, user_id: UUID, sha256: str, image: Image) -> Media:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO media (id, workspace_id, sha256, mime, width, height, size,"
                    " created_by) VALUES (:id, :workspace, :sha256, :mime, :width, :height,"
                    f" :size, :user) RETURNING {COLUMNS}"
                ),
                {
                    "id": uuid4(),
                    "workspace": workspace_id,
                    "sha256": sha256,
                    "mime": image.mime,
                    "width": image.width,
                    "height": image.height,
                    "size": len(image.data),
                    "user": user_id,
                },
            ).one()
        return _media(row)

    def get(self, workspace_id: UUID, media_id: UUID) -> Media | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(f"SELECT {COLUMNS} FROM media WHERE id = :id AND {here()}"),
                {"id": media_id},
            ).one_or_none()
        return None if row is None else _media(row)

    def existing(self, workspace_id: UUID, ids: list[UUID]) -> set[UUID]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            found = connection.execute(
                sa.text(f"SELECT id FROM media WHERE id = ANY(:ids) AND {here()}"),
                {"ids": ids},
            ).scalars()
            return set(found)
