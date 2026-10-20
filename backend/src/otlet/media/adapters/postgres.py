# SPDX-License-Identifier: AGPL-3.0-or-later
"""The description of the images of each workspace, on PostgreSQL."""

from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.media.domain.media import Description, Image, Media
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here

COLUMNS = (
    "id, sha256, mime, width, height, size, created_at, name, description, origin, in_bank,"
    " credit, licence, source_url, thumbnail_sha256, tags"
)
SEARCHED = "lower(concat_ws(' ', name, description, credit, licence, array_to_string(tags, ' ')))"
LISTED = 1000  # a médiathèque larger than this is searched, not scrolled


def _media(row: sa.Row[Any]) -> Media:
    return Media(
        id=row.id,
        sha256=row.sha256,
        mime=row.mime,
        width=row.width,
        height=row.height,
        size=row.size,
        created_at=row.created_at,
        name=row.name,
        description=row.description,
        origin=row.origin,
        in_bank=row.in_bank,
        credit=row.credit,
        licence=row.licence,
        source_url=row.source_url,
        thumbnail_sha256=row.thumbnail_sha256,
        tags=tuple(row.tags),
    )


class PostgresMediaStore:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

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
    ) -> Media:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO media (id, workspace_id, sha256, mime, width, height, size,"
                    " created_by, name, origin, thumbnail_sha256, in_bank) VALUES (:id,"
                    " :workspace, :sha256, :mime, :width, :height, :size, :user, :name, :origin,"
                    f" :thumbnail, :in_bank) RETURNING {COLUMNS}"
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
                    "name": name,
                    "origin": origin,
                    "thumbnail": thumbnail,
                    "in_bank": in_bank,
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

    def search(self, workspace_id: UUID, query: str, tag: str | None = None) -> list[Media]:
        """The images whose name, description, credit, licence or tags hold `query`, newest
        first; with `tag`, those that bear it."""
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {COLUMNS} FROM media WHERE {here()}"
                    f" AND (:query = '' OR strpos({SEARCHED}, lower(:query)) > 0)"
                    " AND (CAST(:tag AS text) IS NULL OR :tag = ANY(tags))"
                    " ORDER BY created_at DESC, id LIMIT :limit"
                ),
                {"query": query, "tag": tag, "limit": LISTED},
            ).all()
        return [_media(row) for row in rows]

    def describe(
        self, workspace_id: UUID, media_id: UUID, description: Description
    ) -> Media | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "UPDATE media SET name = :name, description = :description,"
                    " credit = :credit, licence = :licence, source_url = :source_url"
                    f" WHERE id = :id AND {here()} RETURNING {COLUMNS}"
                ),
                {
                    "id": media_id,
                    "name": description.name,
                    "description": description.description,
                    "credit": description.credit,
                    "licence": description.licence,
                    "source_url": description.source_url,
                },
            ).one_or_none()
        return None if row is None else _media(row)

    def keep(self, workspace_id: UUID, media_id: UUID, in_bank: bool) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            return (
                connection.execute(
                    sa.text(
                        f"UPDATE media SET in_bank = :in_bank WHERE id = :id AND {here()}"
                        " RETURNING id"
                    ),
                    {"id": media_id, "in_bank": in_bank},
                ).scalar_one_or_none()
                is not None
            )

    def set_tags(self, workspace_id: UUID, media_id: UUID, tags: tuple[str, ...]) -> Media | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"UPDATE media SET tags = :tags WHERE id = :id AND {here()} RETURNING {COLUMNS}"
                ),
                {"id": media_id, "tags": list(tags)},
            ).one_or_none()
        return None if row is None else _media(row)

    def tags(self, workspace_id: UUID) -> list[str]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            found = connection.execute(
                sa.text(
                    f"SELECT DISTINCT unnest(tags) AS tag FROM media WHERE {here()} ORDER BY tag"
                )
            ).scalars()
            return list(found)

    def set_thumbnail(self, workspace_id: UUID, media_id: UUID, sha256: str) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(f"UPDATE media SET thumbnail_sha256 = :sha256 WHERE id = :id AND {here()}"),
                {"id": media_id, "sha256": sha256},
            )

    def delete(self, workspace_id: UUID, media_id: UUID) -> bool:
        """The row only: its files may be another workspace's too (ADR-0040)."""
        with workspace_transaction(self._engine, workspace_id) as connection:
            return (
                connection.execute(
                    sa.text(f"DELETE FROM media WHERE id = :id AND {here()} RETURNING id"),
                    {"id": media_id},
                ).scalar_one_or_none()
                is not None
            )
