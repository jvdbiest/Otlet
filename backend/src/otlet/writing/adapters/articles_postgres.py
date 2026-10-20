# SPDX-License-Identifier: AGPL-3.0-or-later
"""Articles, versions and generations on PostgreSQL, in the context of each workspace."""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa

from otlet.collection.adapters.postgres import ITEM_COLUMNS, ITEMS_FROM, item_from_row
from otlet.jobs.application.registry import Enqueue
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here
from otlet.writing.application.drafts import GENERATE_DRAFT, Written
from otlet.writing.domain.article import Article, Generation, LibraryEntry, Version
from otlet.writing.domain.document import body_text
from otlet.writing.domain.draft import PROMPT_VERSION, SourceText

GENERATION_COLUMNS = (
    "id, brief_id, status, error, article_id, version, attempts, created_at, finished_at, details"
)
VERSION_COLUMNS = (
    "number, title, document, origin, provider_kind, model, prompt_version, cut_sources,"
    " unused_sources, context_overflow, created_at, updated_at, based_on"
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
        details=row.details,
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
        context_overflow=row.context_overflow,
        created_at=row.created_at,
        details=row.details,
        updated_at=row.updated_at,
        based_on=row.based_on,
    )


# The details of the generation that made a version, if any.
DETAILS = (
    "coalesce((SELECT g.details FROM article_generations AS g"
    " WHERE g.article_id = article_versions.article_id"
    " AND g.version = article_versions.number"
    " AND g.workspace_id = article_versions.workspace_id), '{}') AS details"
)


# The topics of an article are those of the items of its brief (Joël, 2026-10-20): read where
# the watch keeps them, never copied, so that a topic renamed or removed follows.
TOPICS_OF = (
    "(SELECT coalesce(json_agg(DISTINCT jsonb_build_object('id', t.id, 'name', t.name)), '[]')"
    " FROM brief_items AS bi JOIN topic_matches AS m"
    " ON m.item_id = bi.item_id AND m.workspace_id = bi.workspace_id"
    " JOIN topics AS t ON t.id = m.topic_id AND t.workspace_id = m.workspace_id"
    " WHERE bi.brief_id = a.brief_id AND bi.workspace_id = a.workspace_id)"
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
        context_overflow: bool,
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
                    " unused_sources, context_overflow, created_by, body_text)"
                    " SELECT :workspace, :article, coalesce(max(number), 0) + 1, :title,"
                    " CAST(:document AS jsonb), 'ia', :provider, :model, :prompt,"
                    " CAST(:cut AS jsonb), CAST(:unused AS jsonb), :overflow, :user, :body"
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
                    "overflow": context_overflow,
                    "user": user_id,
                    "body": body_text(document),
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
        details: dict[str, Any],
    ) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE article_generations SET status = :status, error = :error,"
                    " attempts = CAST(:attempts AS jsonb), article_id = :article,"
                    " version = :version, details = CAST(:details AS jsonb), finished_at = now()"
                    # A generation cancelled meanwhile stays cancelled.
                    f" WHERE id = :id AND status = 'running' AND {here()}"
                ),
                {
                    "id": generation_id,
                    "status": "failed" if error is not None else "done",
                    "error": error,
                    "attempts": json.dumps(list(attempts)),
                    "article": None if article is None else article[0],
                    "version": None if article is None else article[1],
                    "details": json.dumps(details),
                },
            )

    def cancel(self, workspace_id: UUID, brief_id: UUID) -> Generation | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "UPDATE article_generations SET status = 'failed', error = 'cancelled',"
                    " finished_at = now()"
                    f" WHERE brief_id = :brief AND status = 'running' AND {here()}"
                    f" RETURNING {GENERATION_COLUMNS}"
                ),
                {"brief": brief_id},
            ).first()
        return None if row is None else _generation(row)

    def clear_details(self, workspace_id: UUID, brief_id: UUID) -> int:
        with workspace_transaction(self._engine, workspace_id) as connection:
            cleared = connection.execute(
                sa.text(
                    "UPDATE article_generations SET details = '{}', attempts = '[]'"
                    f" WHERE brief_id = :brief AND {here()} AND status <> 'running'"
                ),
                {"brief": brief_id},
            ).rowcount
        return cleared

    def article_of(self, workspace_id: UUID, brief_id: UUID) -> Article | None:
        return self._article(workspace_id, "brief_id = :key", brief_id)

    def article(self, workspace_id: UUID, article_id: UUID) -> Article | None:
        return self._article(workspace_id, "id = :key", article_id)

    def _article(self, workspace_id: UUID, where: str, key: UUID) -> Article | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "SELECT id, brief_id, title, created_at, updated_at, status,"
                    " validated_version, sent_at, tags FROM articles"
                    f" WHERE {where} AND {here()}"
                ),
                {"key": key},
            ).one_or_none()
            if row is None:
                return None
            versions = connection.execute(
                sa.text(
                    f"SELECT {VERSION_COLUMNS}, {DETAILS} FROM article_versions"
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
            status=row.status,
            validated_version=row.validated_version,
            sent_at=row.sent_at,
            tags=tuple(row.tags),
        )

    def validated_version(self, workspace_id: UUID, article_id: UUID) -> int | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            found: int | None = connection.execute(
                sa.text(f"SELECT validated_version FROM articles WHERE id = :id AND {here()}"),
                {"id": article_id},
            ).scalar()
        return found

    def send(self, workspace_id: UUID, article_id: UUID, number: int) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            sent = connection.execute(
                sa.text(
                    "UPDATE articles SET status = 'valide', validated_version = :number,"
                    " sent_at = coalesce(sent_at, now()), updated_at = now()"
                    f" WHERE id = :article AND {here()} AND EXISTS (SELECT 1 FROM article_versions"
                    " AS v WHERE v.article_id = articles.id AND v.number = :number"
                    " AND v.workspace_id = articles.workspace_id)"
                ),
                {"article": article_id, "number": number},
            ).rowcount
        return sent == 1

    def archive(self, workspace_id: UUID, article_id: UUID, archived: bool) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            changed = connection.execute(
                sa.text(
                    "UPDATE articles SET status = CASE WHEN :archived THEN 'archive'"
                    " WHEN validated_version IS NULL THEN 'brouillon' ELSE 'valide' END,"
                    f" updated_at = now() WHERE id = :article AND {here()}"
                ),
                {"article": article_id, "archived": archived},
            ).rowcount
        return changed == 1

    def set_tags(self, workspace_id: UUID, article_id: UUID, tags: Sequence[str]) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            changed = connection.execute(
                sa.text(f"UPDATE articles SET tags = :tags WHERE id = :article AND {here()}"),
                {"article": article_id, "tags": list(tags)},
            ).rowcount
        return changed == 1

    def library(
        self,
        workspace_id: UUID,
        query: str,
        status: str | None,
        tag: str | None,
        topic_id: UUID | None = None,
    ) -> list[LibraryEntry]:
        """The articles sent to the Library, the latest changed first; the archived ones only
        when asked for. `query` searches the title and the text of the latest version."""
        conditions = ["a.sent_at IS NOT NULL", here("a")]
        values: dict[str, Any] = {"query": query, "tag": tag}
        if status is None:
            conditions.append("a.status <> 'archive'")
        else:
            conditions.append("a.status = :status")
            values["status"] = status
        if tag:
            conditions.append(":tag = ANY(a.tags)")
        if topic_id is not None:
            conditions.append(
                "EXISTS (SELECT 1 FROM brief_items AS bi JOIN topic_matches AS m"
                " ON m.item_id = bi.item_id AND m.workspace_id = bi.workspace_id"
                " WHERE bi.brief_id = a.brief_id AND bi.workspace_id = a.workspace_id"
                " AND m.topic_id = :topic)"
            )
            values["topic"] = topic_id
        search = "websearch_to_tsquery('french', :query)"
        if query.strip():
            conditions.append(f"to_tsvector('french', a.title || ' ' || v.body_text) @@ {search}")
            excerpt = (
                f"ts_headline('french', v.body_text, {search},"
                " 'MaxWords=28, MinWords=12, StartSel=«, StopSel=», MaxFragments=1')"
            )
        else:
            excerpt = "left(v.body_text, 220)"
        rows_sql = (
            "SELECT a.id, a.brief_id, a.title, a.status, a.validated_version, a.tags,"
            f" a.sent_at, a.updated_at, v.number AS current_version, {excerpt} AS excerpt,"
            f" {TOPICS_OF} AS topics"
            " FROM articles AS a JOIN LATERAL (SELECT number, body_text FROM article_versions"
            " WHERE article_id = a.id AND workspace_id = a.workspace_id ORDER BY number DESC"
            f" LIMIT 1) AS v ON true WHERE {' AND '.join(conditions)}"
            " ORDER BY a.updated_at DESC LIMIT 1000"
        )
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(sa.text(rows_sql), values).all()
        return [
            LibraryEntry(
                id=r.id,
                brief_id=r.brief_id,
                title=r.title,
                status=r.status,
                validated_version=r.validated_version,
                current_version=r.current_version,
                tags=tuple(r.tags),
                sent_at=r.sent_at,
                updated_at=r.updated_at,
                excerpt=" ".join(r.excerpt.split()),
                topics=tuple(
                    sorted(((UUID(t["id"]), t["name"]) for t in r.topics), key=lambda t: t[1])
                ),
            )
            for r in rows
        ]

    def library_topics(self, workspace_id: UUID) -> list[tuple[UUID, str]]:
        """The topics the articles of the Library carry, by name."""
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT DISTINCT t.id, t.name FROM articles AS a"
                    " JOIN brief_items AS bi ON bi.brief_id = a.brief_id"
                    " AND bi.workspace_id = a.workspace_id"
                    " JOIN topic_matches AS m ON m.item_id = bi.item_id"
                    " AND m.workspace_id = bi.workspace_id"
                    " JOIN topics AS t ON t.id = m.topic_id AND t.workspace_id = m.workspace_id"
                    f" WHERE a.sent_at IS NOT NULL AND {here('a')} ORDER BY t.name"
                )
            ).all()
        return [(r.id, r.name) for r in rows]

    def tags(self, workspace_id: UUID) -> list[str]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            found = connection.execute(
                sa.text(
                    "SELECT DISTINCT unnest(tags) AS tag FROM articles"
                    f" WHERE {here()} AND sent_at IS NOT NULL ORDER BY tag"
                )
            ).scalars()
            return list(found)

    def version(self, workspace_id: UUID, article_id: UUID, number: int) -> Version | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT {VERSION_COLUMNS}, {DETAILS} FROM article_versions"
                    f" WHERE article_id = :article AND number = :number AND {here()}"
                ),
                {"article": article_id, "number": number},
            ).one_or_none()
        return None if row is None else _version(row)

    def update_version(
        self,
        workspace_id: UUID,
        article_id: UUID,
        number: int,
        title: str,
        document: dict[str, Any],
        updated_at: datetime,
    ) -> Version | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "UPDATE article_versions SET title = :title,"
                    " document = CAST(:document AS jsonb), body_text = :body, updated_at = now()"
                    " WHERE article_id = :article AND number = :number AND origin = 'humain'"
                    f" AND updated_at = :updated_at AND {here()}"
                    f" RETURNING {VERSION_COLUMNS}, {DETAILS}"
                ),
                {
                    "article": article_id,
                    "number": number,
                    "title": title,
                    "document": json.dumps(document),
                    "body": body_text(document),
                    "updated_at": updated_at,
                },
            ).one_or_none()
            if row is not None:
                _touch(connection, article_id, title)
        return None if row is None else _version(row)

    def add_person_version(
        self,
        workspace_id: UUID,
        user_id: UUID,
        article_id: UUID,
        based_on: int,
        title: str,
        document: dict[str, Any],
    ) -> Version:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO article_versions (workspace_id, article_id, number, title,"
                    " document, origin, based_on, created_by, body_text)"
                    " SELECT :workspace, :article, coalesce(max(number), 0) + 1, :title,"
                    " CAST(:document AS jsonb), 'humain', :based_on, :user, :body"
                    f" FROM article_versions WHERE article_id = :article AND {here()}"
                    f" RETURNING {VERSION_COLUMNS}, {DETAILS}"
                ),
                {
                    "workspace": workspace_id,
                    "article": article_id,
                    "title": title,
                    "document": json.dumps(document),
                    "based_on": based_on,
                    "user": user_id,
                    "body": body_text(document),
                },
            ).one()
            _touch(connection, article_id, title)
        return _version(row)

    def create_article(
        self,
        workspace_id: UUID,
        user_id: UUID,
        title: str,
        document: dict[str, Any],
        tags: Sequence[str] = (),
    ) -> UUID:
        """An article without a brief, in the Library at once (Joël, 2026-10-20): written by a
        person, or a copy of another; its first version is theirs."""
        article_id = uuid4()
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO articles (id, workspace_id, brief_id, created_by, title, status,"
                    " sent_at, tags) VALUES (:id, :workspace, NULL, :user, :title, 'brouillon',"
                    " now(), :tags)"
                ),
                {
                    "id": article_id,
                    "workspace": workspace_id,
                    "user": user_id,
                    "title": title,
                    "tags": list(tags),
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO article_versions (workspace_id, article_id, number, title,"
                    " document, origin, created_by, body_text)"
                    " VALUES (:workspace, :article, 1, :title, CAST(:document AS jsonb), 'humain',"
                    " :user, :body)"
                ),
                {
                    "workspace": workspace_id,
                    "article": article_id,
                    "title": title,
                    "document": json.dumps(document),
                    "user": user_id,
                    "body": body_text(document),
                },
            )
        return article_id

    # Where the images are shown (médiathèque, ADR-0040): read in the blocks of the versions,
    # so always true, and kept by no one.

    def media_counts(self, workspace_id: UUID) -> dict[UUID, int]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT block -> 'attrs' ->> 'media' AS media,"
                    " count(DISTINCT v.article_id) AS articles FROM article_versions v,"
                    " jsonb_array_elements(CASE WHEN jsonb_typeof(v.document -> 'content')"
                    " = 'array' THEN v.document -> 'content' ELSE '[]'::jsonb END) AS block"
                    f" WHERE block ->> 'type' = 'image' AND {here('v')} GROUP BY 1"
                )
            ).all()
        counts = {}
        for row in rows:
            try:
                counts[UUID(row.media)] = row.articles
            except (TypeError, ValueError):
                continue  # never written: a version's images are checked
        return counts

    def media_usages(
        self, workspace_id: UUID, media_id: UUID
    ) -> list[tuple[UUID, str, str, tuple[int, ...]]]:
        probe = json.dumps([{"type": "image", "attrs": {"media": str(media_id)}}])
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT a.id, a.title, a.status, array_agg(v.number ORDER BY v.number)"
                    " AS versions FROM article_versions v JOIN articles a ON a.id = v.article_id"
                    f" AND {here('a')} WHERE {here('v')}"
                    " AND v.document -> 'content' @> CAST(:probe AS jsonb)"
                    " GROUP BY a.id, a.title, a.status ORDER BY a.title, a.id"
                ),
                {"probe": probe},
            ).all()
        return [(row.id, row.title, row.status, tuple(row.versions)) for row in rows]

    def delete_archived(self, workspace_id: UUID, article_id: UUID) -> bool:
        """Deletes an archived article and its versions for good (Joël, 2026-10-20: archived
        first, deleted after). Its brief stays; its generations forget it."""
        with workspace_transaction(self._engine, workspace_id) as connection:
            deleted = connection.execute(
                sa.text(
                    "DELETE FROM articles WHERE id = :id AND status = 'archive'"
                    f" AND {here()} RETURNING id"
                ),
                {"id": article_id},
            ).scalar_one_or_none()
            if deleted is None:
                return False
            connection.execute(
                sa.text(
                    "UPDATE article_generations SET article_id = NULL"
                    f" WHERE article_id = :id AND {here()}"
                ),
                {"id": article_id},
            )
            return True

    def discard_untouched(self, workspace_id: UUID, article_id: UUID, number: int) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            removed = connection.execute(
                sa.text(
                    "DELETE FROM article_versions WHERE article_id = :article"
                    " AND number = :number AND origin = 'humain' AND updated_at = created_at"
                    f" AND {here()}"
                ),
                {"article": article_id, "number": number},
            ).rowcount
        return removed == 1


def _touch(connection: sa.Connection, article_id: UUID, title: str) -> None:
    connection.execute(
        sa.text(
            f"UPDATE articles SET title = :title, updated_at = now() WHERE id = :id AND {here()}"
        ),
        {"id": article_id, "title": title},
    )
