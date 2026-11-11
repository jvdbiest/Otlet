# SPDX-License-Identifier: AGPL-3.0-or-later
"""Publishing (U07, docs/design/PUBLICATION_WORDPRESS.md): the WordPress sites of a workspace,
and the sends of an article, as a draft or published. The API records; the worker sends (DR6)."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.platform.secrets import SecretError
from otlet.publishing.application.publishing import Publishing
from otlet.publishing.domain.model import (
    NAME_MAX,
    PASSWORD_MAX,
    TAG_MAX,
    TERMS_MAX,
    URL_MAX,
    USERNAME_MAX,
    Action,
    Event,
    Publication,
    PublishingError,
    Site,
)
from otlet.workspaces.domain.model import WorkspaceContext


class TermView(BaseModel):
    id: int
    name: str


class SiteView(BaseModel):
    id: UUID
    name: str
    url: str
    username: str
    password_hint: str  # the last characters of the application password
    check_result: str | None  # ok, or why the last « Tester » failed; None: never tested
    check_detail: str | None
    check_role: str | None  # the role of the account: author is advised (ADR-0026 §5)
    checked_at: datetime | None
    check_pending: bool
    categories: list[TermView]
    tags: list[TermView]

    @classmethod
    def of(cls, site: Site) -> "SiteView":
        return cls(
            id=site.id,
            name=site.name,
            url=site.url,
            username=site.username,
            password_hint=site.password_hint,
            check_result=site.check_result,
            check_detail=site.check_detail,
            check_role=site.check_role,
            checked_at=site.checked_at,
            check_pending=site.check_pending,
            categories=[TermView(id=t.id, name=t.name) for t in site.categories],
            tags=[TermView(id=t.id, name=t.name) for t in site.tags],
        )


class SiteBody(BaseModel):
    name: str = Field(max_length=NAME_MAX)
    url: str = Field(max_length=URL_MAX)
    username: str = Field(max_length=USERNAME_MAX)
    # Required to add a site; left blank on a change, it keeps the sealed one.
    password: str | None = Field(default=None, max_length=PASSWORD_MAX)


class PublicationView(BaseModel):
    id: UUID
    site_id: UUID
    action: Literal["draft", "publish"]
    asked_version: int
    state: Literal["pending", "done", "failed", "to_check"]
    error: str | None
    remote_id: int | None
    remote_status: str | None  # draft or publish in WordPress
    remote_url: str | None
    version: int | None  # the version of Otlet the post holds
    sent_at: datetime | None
    categories: list[int]
    tags: list[str]
    updated_at: datetime | None

    @classmethod
    def of(cls, p: Publication) -> "PublicationView":
        return cls(
            id=p.id,
            site_id=p.site_id,
            action=p.action.value,
            asked_version=p.asked_version,
            state=p.state.value,
            error=p.error,
            remote_id=p.remote_id,
            remote_status=p.remote_status,
            remote_url=p.remote_url,
            version=p.version,
            sent_at=p.sent_at,
            categories=list(p.categories),
            tags=list(p.tags),
            updated_at=p.updated_at,
        )


class SendBody(BaseModel):
    site_id: UUID
    # draft: « Envoyer en brouillon », the default; publish: « Publier », confirmed by the author.
    action: Literal["draft", "publish"] = "draft"
    categories: list[int] = Field(default_factory=list, max_length=TERMS_MAX)
    tags: list[Annotated[str, Field(max_length=TAG_MAX)]] = Field(
        default_factory=list, max_length=TERMS_MAX
    )


class EventView(BaseModel):
    at: datetime | None
    action: str
    version: int
    result: str
    detail: str | None
    remote_status: str | None

    @classmethod
    def of(cls, e: Event) -> "EventView":
        return cls(
            at=e.at,
            action=e.action,
            version=e.version,
            result=e.result,
            detail=e.detail,
            remote_status=e.remote_status,
        )


CODES = {
    "site_not_found": status.HTTP_404_NOT_FOUND,
    "not_validated": status.HTTP_409_CONFLICT,
    "too_close_blocked": status.HTTP_409_CONFLICT,
    "too_close_pending": status.HTTP_409_CONFLICT,
    "already_published": status.HTTP_409_CONFLICT,
    "send_running": status.HTTP_409_CONFLICT,
    "name_taken": status.HTTP_409_CONFLICT,
}


def _refused(error: PublishingError) -> HTTPException:
    return HTTPException(CODES.get(error.code, status.HTTP_422_UNPROCESSABLE_CONTENT), error.code)


def build_router(
    publishing: Publishing, workspace_context: Callable[..., WorkspaceContext]
) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(prefix=PREFIX + "/{workspace_id}", dependencies=[Depends(same_origin)])

    @router.get("/publishing/sites")
    def list_sites(context: Context) -> list[SiteView]:
        return [SiteView.of(s) for s in publishing.sites(context)]

    @router.post("/publishing/sites", status_code=status.HTTP_201_CREATED)
    def add_site(body: SiteBody, context: Context) -> SiteView:
        """Adds a WordPress site; its application password is sealed at once, and « Tester »
        starts by itself."""
        try:
            site = publishing.add_site(
                context,
                name=body.name,
                url=body.url,
                username=body.username,
                password=body.password or "",
            )
        except PublishingError as error:
            raise _refused(error) from error
        except SecretError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "secrets_unavailable"
            ) from error
        return SiteView.of(site)

    @router.put("/publishing/sites/{site_id}")
    def update_site(site_id: UUID, body: SiteBody, context: Context) -> SiteView:
        try:
            site = publishing.update_site(
                context,
                site_id,
                name=body.name,
                url=body.url,
                username=body.username,
                password=body.password,
            )
        except PublishingError as error:
            raise _refused(error) from error
        except SecretError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "secrets_unavailable"
            ) from error
        if site is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "site_not_found")
        return SiteView.of(site)

    @router.delete("/publishing/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_site(site_id: UUID, context: Context) -> None:
        if not publishing.delete_site(context, site_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "site_not_found")

    @router.post("/publishing/sites/{site_id}/check", status_code=status.HTTP_202_ACCEPTED)
    def check_site(site_id: UUID, context: Context) -> SiteView:
        """« Tester »: the worker connects; the site shows the result when it is done."""
        site = publishing.check_site(context, site_id)
        if site is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "site_not_found")
        return SiteView.of(site)

    @router.get("/articles/{article_id}/publications")
    def list_publications(article_id: UUID, context: Context) -> list[PublicationView]:
        return [PublicationView.of(p) for p in publishing.publications(context, article_id)]

    @router.post("/articles/{article_id}/publications", status_code=status.HTTP_202_ACCEPTED)
    def send(article_id: UUID, body: SendBody, context: Context) -> PublicationView:
        """Sends the validated version: as a draft, or published (never without a click of the
        author). The same WordPress post is updated by every later send."""
        try:
            publication = publishing.send(
                context, article_id, body.site_id, Action(body.action), body.categories, body.tags
            )
        except PublishingError as error:
            raise _refused(error) from error
        return PublicationView.of(publication)

    @router.get("/publications/{publication_id}/events")
    def list_events(publication_id: UUID, context: Context) -> list[EventView]:
        return [EventView.of(e) for e in publishing.events(context, publication_id)]

    return router
