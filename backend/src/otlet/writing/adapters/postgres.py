# SPDX-License-Identifier: AGPL-3.0-or-later
"""Briefs on PostgreSQL, in the context of each workspace."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here
from otlet.writing.domain.brief import (
    Brief,
    BriefError,
    BriefFields,
    BriefItem,
    Length,
    Mode,
    ModelChoice,
)
from otlet.writing.domain.vocabulary import settled

BRIEF_COLUMNS = (
    "b.id, b.workspace_id, b.created_by, b.title, b.angle, b.instructions, b.audience, b.tone,"
    " b.length, b.mode,"
    " b.language, b.channel, b.provider_id, b.model, b.created_at, b.updated_at"
)
# The items of the brief, in order, with what the brief shows of them.
BRIEF_ITEMS = (
    "(SELECT coalesce(json_agg(json_build_object('id', i.id, 'title', i.title, 'url', i.url,"
    " 'source_id', i.source_id, 'source_name', s.name, 'published_at', i.published_at,"
    # The words a draft may use, as the drafts count them: the full text or the user's entry,
    # else the summary (articles_postgres.sources).
    " 'full_text', i.text_status IN ('full_text', 'manual'),"
    " 'words', coalesce(cardinality(regexp_split_to_array(nullif(btrim(coalesce("
    "CASE WHEN i.text_status IN ('full_text', 'manual') THEN coalesce(i.text, i.feed_content) END,"
    " i.summary, i.title)), ''), '\\s+')), 0))"
    " ORDER BY bi.position), '[]') FROM brief_items AS bi"
    " JOIN source_items AS i ON i.id = bi.item_id AND i.workspace_id = bi.workspace_id"
    " LEFT JOIN sources AS s ON s.id = i.source_id"
    " WHERE bi.brief_id = b.id AND bi.workspace_id = b.workspace_id) AS items"
)


def _brief(row: sa.Row[Any]) -> Brief:
    # A model left without its provider (the provider was removed) means the profile again.
    model = None if row.provider_id is None else ModelChoice(row.provider_id, row.model)
    items = tuple(
        BriefItem(
            id=UUID(item["id"]),
            title=item["title"],
            url=item["url"],
            source_id=None if item["source_id"] is None else UUID(item["source_id"]),
            source_name=item["source_name"],
            published_at=None
            if item["published_at"] is None
            else datetime.fromisoformat(item["published_at"]),
            words=item.get("words", 0),
            full_text=item.get("full_text", True),
        )
        for item in row.items
    )
    return Brief(
        id=row.id,
        workspace_id=row.workspace_id,
        created_by=row.created_by,
        fields=settled(
            BriefFields(
                title=row.title,
                item_ids=tuple(item.id for item in items),
                angle=row.angle,
                instructions=row.instructions,
                audience=row.audience,
                tone=row.tone,
                length=Length(row.length),
                mode=Mode(row.mode),
                language=row.language,
                channel=row.channel,
                model=model,
            )
        ),
        items=items,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _values(fields: BriefFields) -> dict[str, object]:
    return {
        "title": fields.title,
        "angle": fields.angle,
        "instructions": fields.instructions,
        "audience": fields.audience,
        "tone": fields.tone,
        "length": fields.length.value,
        "mode": fields.mode.value,
        "language": fields.language,
        "channel": fields.channel,
        "provider": None if fields.model is None else fields.model.provider_id,
        "model": None if fields.model is None else fields.model.model,
    }


class PostgresBriefStore:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def list_briefs(self, workspace_id: UUID) -> list[Brief]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {BRIEF_COLUMNS}, {BRIEF_ITEMS} FROM briefs AS b"
                    f" WHERE {here('b')} ORDER BY b.updated_at DESC, b.id"
                )
            ).all()
        return [_brief(row) for row in rows]

    def get_brief(self, workspace_id: UUID, brief_id: UUID) -> Brief | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            return self._get(connection, brief_id)

    def create_brief(self, workspace_id: UUID, user_id: UUID, fields: BriefFields) -> Brief:
        brief_id = uuid4()
        with workspace_transaction(self._engine, workspace_id) as connection:
            self._check_items(connection, fields)
            self._write(
                connection,
                "INSERT INTO briefs (id, workspace_id, created_by, title, angle, instructions,"
                " audience, tone, length, mode, language, channel, provider_id, model)"
                " VALUES (:id, :workspace, :user, :title, :angle, :instructions, :audience, :tone,"
                " :length, :mode, :language, :channel, :provider, :model) RETURNING id",
                {"id": brief_id, "workspace": workspace_id, "user": user_id, **_values(fields)},
            )
            self._set_items(connection, workspace_id, brief_id, fields)
            brief = self._get(connection, brief_id)
            if brief is None:  # just inserted in this transaction
                raise LookupError(brief_id)
            return brief

    def update_brief(self, workspace_id: UUID, brief_id: UUID, fields: BriefFields) -> Brief | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            self._check_items(connection, fields)
            found = self._write(
                connection,
                "UPDATE briefs SET title = :title, angle = :angle, instructions = :instructions,"
                " audience = :audience,"
                " tone = :tone, length = :length, mode = :mode, language = :language,"
                " channel = :channel,"
                " provider_id = :provider, model = :model, updated_at = now()"
                f" WHERE id = :id AND {here()} RETURNING id",
                {"id": brief_id, **_values(fields)},
            )
            if found is None:
                return None
            self._set_items(connection, workspace_id, brief_id, fields)
            return self._get(connection, brief_id)

    def delete_brief(self, workspace_id: UUID, brief_id: UUID) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            deleted = connection.execute(
                sa.text(f"DELETE FROM briefs WHERE id = :id AND {here()} RETURNING id"),
                {"id": brief_id},
            ).scalar_one_or_none()
        return deleted is not None

    @staticmethod
    def _get(connection: sa.Connection, brief_id: UUID) -> Brief | None:
        row = connection.execute(
            sa.text(
                f"SELECT {BRIEF_COLUMNS}, {BRIEF_ITEMS} FROM briefs AS b"
                f" WHERE b.id = :id AND {here('b')}"
            ),
            {"id": brief_id},
        ).one_or_none()
        return None if row is None else _brief(row)

    @staticmethod
    def _check_items(connection: sa.Connection, fields: BriefFields) -> None:
        found = connection.execute(
            sa.text(
                "SELECT count(*) FROM source_items AS i"
                f" WHERE i.id = ANY(CAST(:items AS uuid[])) AND {here('i')}"
            ),
            {"items": list(fields.item_ids)},
        ).scalar_one()
        if found != len(fields.item_ids):
            raise BriefError("unknown_item", "an item is not in the workspace")

    @staticmethod
    def _write(connection: sa.Connection, statement: str, values: dict[str, object]) -> object:
        try:
            with connection.begin_nested():
                return connection.execute(sa.text(statement), values).scalar_one_or_none()
        except sa.exc.IntegrityError as error:
            if "briefs_provider_of_author" in str(error.orig):
                raise BriefError(
                    "unknown_provider", "the provider is not one of the author's"
                ) from error
            raise

    @staticmethod
    def _set_items(
        connection: sa.Connection, workspace_id: UUID, brief_id: UUID, fields: BriefFields
    ) -> None:
        connection.execute(
            sa.text(f"DELETE FROM brief_items WHERE brief_id = :brief AND {here()}"),
            {"brief": brief_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO brief_items (workspace_id, brief_id, item_id, position)"
                " VALUES (:workspace, :brief, :item, :position)"
            ),
            [
                {"workspace": workspace_id, "brief": brief_id, "item": item_id, "position": n}
                for n, item_id in enumerate(fields.item_ids)
            ],
        )
