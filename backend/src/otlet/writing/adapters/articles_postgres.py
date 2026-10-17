# SPDX-License-Identifier: AGPL-3.0-or-later
"""Articles, versions and generations on PostgreSQL, in the context of each workspace."""

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.collection.adapters.postgres import ITEM_COLUMNS, ITEMS_FROM, item_from_row
from otlet.jobs.application.registry import Enqueue
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here
from otlet.writing.application.drafts import GENERATE_DRAFT, Written
from otlet.writing.domain.article import Article, Generation, Version
from otlet.writing.domain.draft import PROMPT_VERSION, SourceText

GENERATION_COLUMNS = (
    "id, brief_id, status, error, article_id, version, attempts, created_at, finished_at"
)
VERSION_COLUMNS = (
    "number, title, document, origin, provider_kind, model, prompt_version, cut_sources,"
    " unused_sources, created_at"
)


def _generation(row: sa.Row[Any]) -> Generation:
    return Generation(
        id=row.id,
        brief_id=row.brief_id,
        status=row.status,
        error=row.error,
        article_id=row.article_id,
        version=row.version,
        attempts=tuple(row.attempts),
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


def _version(row: sa.Row[Any]) -> Version:
    return Version(
        number=row.number,
        title=row.title,
        document=row.document,
        origin=row.origin,
        provider_kind=row.provider_kind,
        model=row.model,
        prompt_version=row.prompt_version,
        cut_sources=tuple(row.cut_sources),
        unused_sources=tuple(row.unused_sources),
        created_at=row.created_at,
    )


class PostgresArticleStore:
    def __init__(self, engine: sa.Engine, enqueue: Enqueue) -> None:
        self._engine = engine
        self._enqueue = enqueue

    def start(self, workspace_id: UUID, user_id: UUID, brief_id: UUID) -> Generation:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO article_generations (id, workspace_id, brief_id, created_by)"
                    f" VALUES (:id, :workspace, :brief, :user) RETURNING {GENERATION_COLUMNS}"
                ),
                {"id": uuid4(), "workspace": workspace_id, "brief": brief_id, "user": user_id},
            ).one()
            self._enqueue(
                connection,
                GENERATE_DRAFT,
                workspace_id=str(workspace_id),
                user_id=str(user_id),
                generation_id=str(row.id),
            )
        return _generation(row)

    def generation(self, workspace_id: UUID, generation_id: UUID) -> Generation | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT {GENERATION_COLUMNS} FROM article_generations"
                    f" WHERE id = :id AND {here()}"
                ),
                {"id": generation_id},
            ).one_or_none()
        return None if row is None else _generation(row)

    def latest_generation(self, workspace_id: UUID, brief_id: UUID) -> Generation | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT {GENERATION_COLUMNS} FROM article_generations"
                    f" WHERE brief_id = :brief AND {here()} ORDER BY created_at DESC, id LIMIT 1"
                ),
                {"brief": brief_id},
            ).one_or_none()
        return None if row is None else _generation(row)

    def sources(self, workspace_id: UUID, brief_id: UUID) -> list[SourceText]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {ITEM_COLUMNS} FROM brief_items AS bi"
                    f" JOIN {ITEMS_FROM} ON i.id = bi.item_id AND i.workspace_id = bi.workspace_id"
                    f" WHERE bi.brief_id = :brief AND {here('bi')} ORDER BY bi.position"
                ),
                {"brief": brief_id},
            ).all()
        result = []
        for row in rows:
            item = item_from_row(row)
            # Only what Otlet may use: the full text or the user's entry, else the summary.
            text = item.text or item.summary or item.title
            result.append(
                SourceText(
                    title=item.title,
                    url=item.url,
                    publisher=item.source_name,
                    published_at=item.published_at,
                    text=text,
                )
            )
        return result

    def add_version(
        self,
        workspace_id: UUID,
        user_id: UUID,
        brief_id: UUID,
        title: str,
        document: dict[str, Any],
        written: Written,
        cut_sources: Sequence[str],
        unused_sources: Sequence[str],
    ) -> tuple[UUID, int]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            article_id = connection.execute(
                sa.text(
                    "INSERT INTO articles (id, workspace_id, brief_id, created_by, title)"
                    " VALUES (:id, :workspace, :brief, :user, :title)"
                    " ON CONFLICT (brief_id) DO UPDATE SET title = EXCLUDED.title,"
                    " updated_at = now() RETURNING id"
                ),
                {
                    "id": uuid4(),
                    "workspace": workspace_id,
                    "brief": brief_id,
                    "user": user_id,
                    "title": title,
                },
            ).scalar_one()
            number = connection.execute(
                sa.text(
                    "INSERT INTO article_versions (workspace_id, article_id, number, title,"
                    " document, origin, provider_kind, model, prompt_version, cut_sources,"
                    " unused_sources, created_by)"
                    " SELECT :workspace, :article, coalesce(max(number), 0) + 1, :title,"
                    " CAST(:document AS jsonb), 'ia', :provider, :model, :prompt,"
                    " CAST(:cut AS jsonb), CAST(:unused AS jsonb), :user"
                    f" FROM article_versions WHERE article_id = :article AND {here()}"
                    " RETURNING number"
                ),
                {
                    "workspace": workspace_id,
                    "article": article_id,
                    "title": title,
                    "document": json.dumps(document),
                    "provider": written.provider_kind,
                    "model": written.model,
                    "prompt": PROMPT_VERSION,
                    "cut": json.dumps(list(cut_sources)),
                    "unused": json.dumps(list(unused_sources)),
                    "user": user_id,
                },
            ).scalar_one()
        return article_id, number

    def finish(
        self,
        workspace_id: UUID,
        generation_id: UUID,
        error: str | None,
        attempts: Sequence[dict[str, Any]],
        article: tuple[UUID, int] | None,
    ) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE article_generations SET status = :status, error = :error,"
                    " attempts = CAST(:attempts AS jsonb), article_id = :article,"
                    " version = :version, finished_at = now()"
                    f" WHERE id = :id AND {here()}"
                ),
                {
                    "id": generation_id,
                    "status": "failed" if error is not None else "done",
                    "error": error,
                    "attempts": json.dumps(list(attempts)),
                    "article": None if article is None else article[0],
                    "version": None if article is None else article[1],
                },
            )

    def article_of(self, workspace_id: UUID, brief_id: UUID) -> Article | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "SELECT id, brief_id, title, created_at, updated_at FROM articles"
                    f" WHERE brief_id = :brief AND {here()}"
                ),
                {"brief": brief_id},
            ).one_or_none()
            if row is None:
                return None
            versions = connection.execute(
                sa.text(
                    f"SELECT {VERSION_COLUMNS} FROM article_versions"
                    f" WHERE article_id = :article AND {here()} ORDER BY number"
                ),
                {"article": row.id},
            ).all()
        return Article(
            id=row.id,
            brief_id=row.brief_id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            versions=tuple(_version(v) for v in versions),
        )
