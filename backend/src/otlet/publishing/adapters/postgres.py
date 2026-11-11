# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sites, publications and their journal on PostgreSQL, under row-level security (workspace)."""

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from otlet.jobs.application.registry import Enqueue
from otlet.platform.database import workspace_transaction
from otlet.platform.rls import here
from otlet.publishing.application.publishing import CHECK_SITE, SEND
from otlet.publishing.domain.model import (
    Action,
    Event,
    Publication,
    PublishingError,
    Site,
    State,
    Term,
)
from otlet.workspaces.domain.model import WorkspaceContext

SITE_COLUMNS = (
    "id, workspace_id, name, url, username, password_hint, check_result, check_detail,"
    " check_role, checked_at, check_pending, categories, tags"
)
PUBLICATION_COLUMNS = (
    "id, workspace_id, article_id, site_id, marker, action, asked_version, state, remote_id,"
    " remote_status, remote_url, version, sent_at, error, categories, tags, updated_at"
)


def _terms(raw: Any) -> tuple[Term, ...]:
    return tuple(Term(int(t["id"]), str(t["name"])) for t in raw or [])


def _site(row: sa.Row[Any]) -> Site:
    return Site(
        row.id,
        row.workspace_id,
        row.name,
        row.url,
        row.username,
        row.password_hint,
        row.check_result,
        row.check_detail,
        row.check_role,
        row.checked_at,
        row.check_pending,
        _terms(row.categories),
        _terms(row.tags),
    )


def _publication(row: sa.Row[Any]) -> Publication:
    return Publication(
        row.id,
        row.workspace_id,
        row.article_id,
        row.site_id,
        row.marker,
        Action(row.action),
        row.asked_version,
        State(row.state),
        row.remote_id,
        row.remote_status,
        row.remote_url,
        row.version,
        row.sent_at,
        row.error,
        tuple(row.categories or ()),
        tuple(row.tags or ()),
        row.updated_at,
    )


class PostgresPublishing:
    def __init__(self, engine: sa.Engine, enqueue: Enqueue) -> None:
        self._engine = engine
        self._enqueue = enqueue

    # Sites ------------------------------------------------------------------------------------

    def sites(self, workspace_id: UUID) -> list[Site]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(f"SELECT {SITE_COLUMNS} FROM publishing_sites WHERE {here()} ORDER BY name")
            ).all()
        return [_site(row) for row in rows]

    def site(self, workspace_id: UUID, site_id: UUID) -> Site | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(f"SELECT {SITE_COLUMNS} FROM publishing_sites WHERE {here()} AND id = :id"),
                {"id": site_id},
            ).one_or_none()
        return None if row is None else _site(row)

    def add_site(
        self, context: WorkspaceContext, site: Site, sealed: bytes, enqueue_check: bool
    ) -> Site:
        with workspace_transaction(self._engine, context.workspace_id) as connection:
            try:
                row = connection.execute(
                    sa.text(
                        "INSERT INTO publishing_sites (id, workspace_id, name, url, username,"
                        " password_sealed, password_hint, created_by, check_pending)"
                        " VALUES (:id, :ws, :name, :url, :username, :sealed, :hint, :user,"
                        " :pending)"
                        f" RETURNING {SITE_COLUMNS}"
                    ),
                    {
                        "id": site.id,
                        "ws": context.workspace_id,
                        "name": site.name,
                        "url": site.url,
                        "username": site.username,
                        "sealed": sealed,
                        "hint": site.password_hint,
                        "user": context.user_id,
                        "pending": enqueue_check,
                    },
                ).one()
            except sa.exc.IntegrityError as error:
                raise PublishingError("name_taken", "a site of this name exists") from error
            if enqueue_check:
                self._enqueue(
                    connection,
                    CHECK_SITE,
                    workspace_id=str(context.workspace_id),
                    site_id=str(site.id),
                )
        return _site(row)

    def update_site(
        self, context: WorkspaceContext, site: Site, sealed: bytes | None
    ) -> Site | None:
        with workspace_transaction(self._engine, context.workspace_id) as connection:
            try:
                row = connection.execute(
                    sa.text(
                        "UPDATE publishing_sites SET name = :name, url = :url,"
                        " username = :username,"
                        " password_hint = :hint, check_pending = true,"
                        " password_sealed = COALESCE(:sealed, password_sealed)"
                        f" WHERE {here()} AND id = :id RETURNING {SITE_COLUMNS}"
                    ),
                    {
                        "id": site.id,
                        "name": site.name,
                        "url": site.url,
                        "username": site.username,
                        "hint": site.password_hint,
                        "sealed": sealed,
                    },
                ).one_or_none()
            except sa.exc.IntegrityError as error:
                raise PublishingError("name_taken", "a site of this name exists") from error
            if row is not None:
                self._enqueue(
                    connection,
                    CHECK_SITE,
                    workspace_id=str(context.workspace_id),
                    site_id=str(site.id),
                )
        return None if row is None else _site(row)

    def delete_site(self, workspace_id: UUID, site_id: UUID) -> bool:
        with workspace_transaction(self._engine, workspace_id) as connection:
            deleted = connection.execute(
                sa.text(f"DELETE FROM publishing_sites WHERE {here()} AND id = :id RETURNING id"),
                {"id": site_id},
            ).one_or_none()
        return deleted is not None

    def ask_check(self, workspace_id: UUID, site_id: UUID) -> Site | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "UPDATE publishing_sites SET check_pending = true"
                    f" WHERE {here()} AND id = :id RETURNING {SITE_COLUMNS}"
                ),
                {"id": site_id},
            ).one_or_none()
            if row is not None:
                self._enqueue(
                    connection, CHECK_SITE, workspace_id=str(workspace_id), site_id=str(site_id)
                )
        return None if row is None else _site(row)

    def finish_check(
        self,
        workspace_id: UUID,
        site_id: UUID,
        result: str,
        detail: str | None,
        role: str | None,
        categories: Sequence[Term] | None,
        tags: Sequence[Term] | None,
    ) -> None:
        def terms(found: Sequence[Term] | None) -> str | None:
            return (
                None if found is None else json.dumps([{"id": t.id, "name": t.name} for t in found])
            )

        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE publishing_sites SET check_result = :result, check_detail = :detail,"
                    " check_role = :role, checked_at = now(), check_pending = false,"
                    " categories = COALESCE(CAST(:categories AS jsonb), categories),"
                    " tags = COALESCE(CAST(:tags AS jsonb), tags)"
                    f" WHERE {here()} AND id = :id"
                ),
                {
                    "id": site_id,
                    "result": result,
                    "detail": detail,
                    "role": role,
                    "categories": terms(categories),
                    "tags": terms(tags),
                },
            )

    def password(self, workspace_id: UUID, site_id: UUID) -> bytes | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            sealed = connection.execute(
                sa.text(
                    f"SELECT password_sealed FROM publishing_sites WHERE {here()} AND id = :id"
                ),
                {"id": site_id},
            ).scalar()
        return None if sealed is None else bytes(sealed)

    # Publications -----------------------------------------------------------------------------

    def publications(self, workspace_id: UUID, article_id: UUID) -> list[Publication]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT {PUBLICATION_COLUMNS} FROM publications"
                    f" WHERE {here()} AND article_id = :article ORDER BY created_at"
                ),
                {"article": article_id},
            ).all()
        return [_publication(row) for row in rows]

    def publication(self, workspace_id: UUID, publication_id: UUID) -> Publication | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    f"SELECT {PUBLICATION_COLUMNS} FROM publications WHERE {here()} AND id = :id"
                ),
                {"id": publication_id},
            ).one_or_none()
        return None if row is None else _publication(row)

    def ask_send(self, context: WorkspaceContext, publication: Publication) -> Publication | None:
        """Records the send and enqueues it; None when a send of this article to this site is
        already under way."""
        values = {
            "id": publication.id,
            "ws": context.workspace_id,
            "article": publication.article_id,
            "site": publication.site_id,
            "marker": publication.marker,
            "action": publication.action.value,
            "version": publication.asked_version,
            "categories": list(publication.categories),
            "tags": list(publication.tags),
        }
        with workspace_transaction(self._engine, context.workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO publications (id, workspace_id, article_id, site_id, marker,"
                    " action, asked_version, state, categories, tags)"
                    " VALUES (:id, :ws, :article, :site, :marker, :action, :version, 'pending',"
                    " :categories, :tags)"
                    " ON CONFLICT (article_id, site_id) DO UPDATE SET action = EXCLUDED.action,"
                    " asked_version = EXCLUDED.asked_version, state = 'pending', error = NULL,"
                    " categories = EXCLUDED.categories, tags = EXCLUDED.tags, updated_at = now()"
                    " WHERE publications.state <> 'pending'"
                    f" RETURNING {PUBLICATION_COLUMNS}"
                ),
                values,
            ).one_or_none()
            if row is not None:
                self._enqueue(
                    connection,
                    SEND,
                    workspace_id=str(context.workspace_id),
                    publication_id=str(row.id),
                    user_id=str(context.user_id),
                )
        return None if row is None else _publication(row)

    def finish_send(self, workspace_id: UUID, publication: Publication, event: Event) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE publications SET state = :state, error = :error,"
                    " remote_id = :remote_id, remote_status = :remote_status,"
                    " remote_url = :remote_url, version = :version,"
                    " sent_at = CASE WHEN :state = 'done' THEN now() ELSE sent_at END,"
                    f" updated_at = now() WHERE {here()} AND id = :id"
                ),
                {
                    "id": publication.id,
                    "state": publication.state.value,
                    "error": publication.error,
                    "remote_id": publication.remote_id,
                    "remote_status": publication.remote_status,
                    "remote_url": publication.remote_url,
                    "version": publication.version,
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO publication_events (workspace_id, publication_id, user_id,"
                    " action, version, result, detail, remote_id, remote_status)"
                    " VALUES (:ws, :publication, :user, :action, :version, :result, :detail,"
                    " :remote_id, :remote_status)"
                ),
                {
                    "ws": workspace_id,
                    "publication": publication.id,
                    "user": event.user_id,
                    "action": event.action,
                    "version": event.version,
                    "result": event.result,
                    "detail": event.detail,
                    "remote_id": publication.remote_id,
                    "remote_status": event.remote_status,
                },
            )

    def forget_remote(self, workspace_id: UUID, publication_id: UUID) -> None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE publications SET remote_id = NULL, remote_status = NULL,"
                    f" remote_url = NULL, version = NULL WHERE {here()} AND id = :id"
                ),
                {"id": publication_id},
            )

    def events(self, workspace_id: UUID, publication_id: UUID) -> list[Event]:
        with workspace_transaction(self._engine, workspace_id) as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT at, action, version, result, detail, remote_status, user_id"
                    f" FROM publication_events WHERE {here()} AND publication_id = :id"
                    " ORDER BY at DESC, id DESC LIMIT 50"
                ),
                {"id": publication_id},
            ).all()
        return [
            Event(r.at, r.action, r.version, r.result, r.detail, r.remote_status, r.user_id)
            for r in rows
        ]


class PostgresValidated:
    """The validated version of an article of the Library, as `Articles` wants it; the gate of
    U05 comes from the writing module."""

    def __init__(self, engine: sa.Engine, gate: Any) -> None:
        self._engine = engine
        self._gate = gate

    def validated(self, workspace_id: UUID, article_id: UUID) -> tuple[int, str, Any] | None:
        with workspace_transaction(self._engine, workspace_id) as connection:
            row = connection.execute(
                sa.text(
                    "SELECT v.number, v.title, v.document FROM articles a"
                    " JOIN article_versions v ON v.article_id = a.id"
                    " AND v.number = a.validated_version"
                    f" WHERE {here('a')} AND a.id = :id AND a.status = 'valide'"
                ),
                {"id": article_id},
            ).one_or_none()
        return None if row is None else (row.number, row.title, row.document)

    def gate(self, workspace_id: UUID, article_id: UUID, number: int) -> str:
        return str(self._gate(workspace_id, article_id, number))
