# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sites and sends (U07, docs/design/PUBLICATION_WORDPRESS.md).

The API records a site (its password sealed) or a send, and enqueues the work; the worker alone
opens the password and talks to WordPress (DR6). Nothing leaves without a click of the author:
« Envoyer en brouillon » is the default, « Publier » is confirmed in the interface.
"""

import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any, Protocol
from uuid import UUID

from otlet.publishing.domain.model import (
    Action,
    Event,
    Post,
    Publication,
    PublishingError,
    Site,
    State,
    Term,
    check_name,
    check_password,
    check_terms,
    check_url,
    check_username,
    has_marker,
    marker_comment,
    marker_slug,
    password_hint,
    plan,
)
from otlet.workspaces.domain.model import WorkspaceContext

CHECK_SITE = "publishing.check_site"
SEND = "publishing.send"
PASSWORD_CONTEXT = "publishing-site:"  # noqa: S105 (a label, not a password)
RECONCILE_WAIT_SECONDS = 5.0  # ADR-0026 §2: two searches of the marker, 5 s apart


def password_context(site_id: UUID) -> bytes:
    return f"{PASSWORD_CONTEXT}{site_id}".encode()


class Store(Protocol):
    def sites(self, workspace_id: UUID) -> list[Site]: ...

    def site(self, workspace_id: UUID, site_id: UUID) -> Site | None: ...

    def add_site(
        self, context: WorkspaceContext, site: Site, sealed: bytes, enqueue_check: bool
    ) -> Site: ...

    def update_site(
        self, context: WorkspaceContext, site: Site, sealed: bytes | None
    ) -> Site | None: ...

    def delete_site(self, workspace_id: UUID, site_id: UUID) -> bool: ...

    def ask_check(self, workspace_id: UUID, site_id: UUID) -> Site | None: ...

    def finish_check(
        self,
        workspace_id: UUID,
        site_id: UUID,
        result: str,
        detail: str | None,
        role: str | None,
        categories: Sequence[Term] | None,
        tags: Sequence[Term] | None,
    ) -> None: ...

    def publications(self, workspace_id: UUID, article_id: UUID) -> list[Publication]: ...

    def publication(self, workspace_id: UUID, publication_id: UUID) -> Publication | None: ...

    def ask_send(
        self, context: WorkspaceContext, publication: Publication
    ) -> Publication | None: ...

    def finish_send(self, workspace_id: UUID, publication: Publication, event: Event) -> None: ...

    def forget_remote(self, workspace_id: UUID, publication_id: UUID) -> None:
        """The post was deleted in WordPress: the next send creates a new one."""
        ...

    def events(self, workspace_id: UUID, publication_id: UUID) -> list[Event]: ...


class Sealer(Protocol):
    def seal(self, plaintext: bytes, context: bytes) -> bytes: ...


class Articles(Protocol):
    """The Library: the validated version of an article, its title and document, and the gate
    of U05 (open, blocked, pending)."""

    def validated(self, workspace_id: UUID, article_id: UUID) -> tuple[int, str, Any] | None: ...

    def gate(self, workspace_id: UUID, article_id: UUID, number: int) -> str: ...


class SiteError(Exception):
    """The site refused or could not be reached; `reason` is stable and safe to show."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class Remote(Protocol):
    """One WordPress site, reached with its password (the worker only)."""

    def me(self) -> str: ...  # the role of the account

    def categories(self) -> list[Term]: ...

    def tags(self) -> list[Term]: ...

    def tag_ids(self, names: Sequence[str]) -> list[int]: ...

    def get(self, post_id: int) -> dict[str, Any] | None: ...

    def find(self, marker: str) -> list[dict[str, Any]]: ...

    def create(self, post: Post) -> dict[str, Any]: ...

    def update(self, post_id: int, post: Post) -> dict[str, Any]: ...


class Publishing:
    def __init__(
        self,
        store: Store,
        sealer: Sealer,
        articles: Articles,
        refuses: Callable[[str], bool],
    ) -> None:
        """`refuses(url)`: an internal address the administrator did not allow (SSRF)."""
        self._store = store
        self._sealer = sealer
        self._articles = articles
        self._refuses = refuses

    # Sites ------------------------------------------------------------------------------------

    def sites(self, context: WorkspaceContext) -> list[Site]:
        return self._store.sites(context.workspace_id)

    def add_site(
        self, context: WorkspaceContext, *, name: str, url: str, username: str, password: str
    ) -> Site:
        site_id = uuid.uuid4()
        secret = check_password(password)
        site = Site(
            site_id,
            context.workspace_id,
            check_name(name),
            self._reachable(url),
            check_username(username),
            password_hint(secret),
        )
        sealed = self._sealer.seal(secret.encode(), password_context(site_id))
        return self._store.add_site(context, site, sealed, enqueue_check=True)

    def update_site(
        self,
        context: WorkspaceContext,
        site_id: UUID,
        *,
        name: str,
        url: str,
        username: str,
        password: str | None,
    ) -> Site | None:
        """A blank password keeps the sealed one: it never comes back to the interface."""
        current = self._store.site(context.workspace_id, site_id)
        if current is None:
            return None
        secret = None if not (password or "").strip() else check_password(password or "")
        site = replace(
            current,
            name=check_name(name),
            url=self._reachable(url),
            username=check_username(username),
            password_hint=current.password_hint if secret is None else password_hint(secret),
        )
        sealed = (
            None
            if secret is None
            else self._sealer.seal(secret.encode(), password_context(site_id))
        )
        return self._store.update_site(context, site, sealed)

    def delete_site(self, context: WorkspaceContext, site_id: UUID) -> bool:
        return self._store.delete_site(context.workspace_id, site_id)

    def check_site(self, context: WorkspaceContext, site_id: UUID) -> Site | None:
        """« Tester »: the worker connects, reads the role and the categories and tags."""
        return self._store.ask_check(context.workspace_id, site_id)

    def _reachable(self, url: str) -> str:
        cleaned = check_url(url)
        if self._refuses(cleaned):
            raise PublishingError(
                "address_not_allowed",
                "an internal address must be allowed by the administrator of the instance",
            )
        return cleaned

    # Sends ------------------------------------------------------------------------------------

    def publications(self, context: WorkspaceContext, article_id: UUID) -> list[Publication]:
        return self._store.publications(context.workspace_id, article_id)

    def events(self, context: WorkspaceContext, publication_id: UUID) -> list[Event]:
        return self._store.events(context.workspace_id, publication_id)

    def send(
        self,
        context: WorkspaceContext,
        article_id: UUID,
        site_id: UUID,
        action: Action,
        categories: list[int],
        tags: list[str],
    ) -> Publication:
        """Records the send of the validated version and enqueues it. Refused at once when the
        article has no validated version, is too close to a source (U05), or when a draft would
        take a published post off line."""
        site = self._store.site(context.workspace_id, site_id)
        if site is None:
            raise PublishingError("site_not_found")
        validated = self._articles.validated(context.workspace_id, article_id)
        if validated is None:
            raise PublishingError("not_validated", "send the article to the Library first")
        number = validated[0]
        gate = self._articles.gate(context.workspace_id, article_id, number)
        if gate != "open":
            raise PublishingError(f"too_close_{gate}")
        chosen_categories, chosen_tags = check_terms(categories, tags)
        current = next(
            (
                p
                for p in self._store.publications(context.workspace_id, article_id)
                if p.site_id == site_id
            ),
            None,
        )
        if current is not None and current.state is State.PENDING:
            raise PublishingError("send_running", "a send of this article is under way")
        plan(action, None if current is None else current.remote_status)
        publication = Publication(
            current.id if current else uuid.uuid4(),
            context.workspace_id,
            article_id,
            site_id,
            current.marker if current else uuid.uuid4().hex,
            action,
            number,
            State.PENDING,
            remote_id=None if current is None else current.remote_id,
            remote_status=None if current is None else current.remote_status,
            remote_url=None if current is None else current.remote_url,
            version=None if current is None else current.version,
            sent_at=None if current is None else current.sent_at,
            categories=chosen_categories,
            tags=chosen_tags,
        )
        recorded = self._store.ask_send(context, publication)
        if recorded is None:
            raise PublishingError("send_running", "a send of this article is under way")
        return recorded


# The worker -----------------------------------------------------------------------------------


def run_check(
    store: Store, remote: Callable[[Site], Remote], workspace_id: UUID, site_id: UUID
) -> None:
    site = store.site(workspace_id, site_id)
    if site is None:
        return
    try:
        client = remote(site)
        role = client.me()
        categories, tags = client.categories(), client.tags()
    except SiteError as error:
        store.finish_check(
            workspace_id, site_id, error.reason, error.detail or None, None, None, None
        )
        return
    store.finish_check(workspace_id, site_id, "ok", None, role, categories, tags)


def run_send(
    store: Store,
    articles: Articles,
    render: Callable[[str, Any], tuple[str, str]],
    remote: Callable[[Site], Remote],
    workspace_id: UUID,
    publication_id: UUID,
    user_id: UUID | None,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """One send, as ADR-0026 asks: find the post (its id, else its marker), create or update it,
    and after a failure look for the marker before saying anything, so that no duplicate is made.
    `render(title, document)` gives the title and the HTML content."""
    publication = store.publication(workspace_id, publication_id)
    if publication is None or publication.state is not State.PENDING:
        return
    number = publication.asked_version
    site = store.site(workspace_id, publication.site_id)

    def finish(
        result: State, error: str | None, post: dict[str, Any] | None, detail: str | None
    ) -> None:
        updated = replace(publication, state=result, error=error)
        if post is not None:
            updated = replace(
                updated,
                remote_id=int(post["id"]),
                remote_status=str(post.get("status") or ""),
                remote_url=str(post.get("link") or "") or None,
                version=number if result is State.DONE else publication.version,
            )
        event = Event(
            at=None,
            action=publication.action.value,
            version=number,
            result=result.value if error is None else error,
            detail=detail,
            remote_status=None if post is None else str(post.get("status") or ""),
            user_id=user_id,
        )
        store.finish_send(workspace_id, updated, event)

    if site is None:
        finish(State.FAILED, "site_not_found", None, None)
        return
    validated = articles.validated(workspace_id, publication.article_id)
    if validated is None or validated[0] != number:
        finish(State.FAILED, "version_changed", None, "the validated version changed: send again")
        return
    if articles.gate(workspace_id, publication.article_id, number) != "open":
        finish(State.FAILED, "too_close", None, None)
        return
    title, content = render(validated[1], validated[2])
    try:
        client = remote(site)
        existing: dict[str, Any] | None = None
        if publication.remote_id is not None:
            existing = client.get(publication.remote_id)
            if existing is None or existing.get("status") == "trash":
                finish(
                    State.FAILED,
                    "remote_deleted",
                    None,
                    "the post was deleted in WordPress: send again to create a new one",
                )
                store.forget_remote(workspace_id, publication.id)
                return
        else:
            found = client.find(publication.marker)
            if len(found) > 1:
                finish(
                    State.TO_CHECK,
                    "several_posts",
                    None,
                    "several posts carry the mark of this article: check them in WordPress",
                )
                return
            existing = found[0] if found else None
        status = plan(publication.action, None if existing is None else str(existing.get("status")))
        post = Post(
            title=title,
            content=f"{marker_comment(publication.marker)}\n{content}",
            status=status,
            # The slug carries the key while the post is a draft. On line, the post takes the
            # slug WordPress makes from the title, and the comment carries the key (ADR-0026 §1):
            # a draft that keeps its otlet-<key> slug is published with an empty one, which
            # WordPress fills from the title (tested on WordPress 7.1.4, 2026-11-11).
            slug=_slug(status, existing, publication.marker),
            categories=publication.categories,
            tags=tuple(client.tag_ids(publication.tags)) if publication.tags else (),
        )
    except PublishingError as error:
        finish(State.FAILED, error.code, None, None)
        return
    except SiteError as error:
        finish(State.FAILED, error.reason, None, error.detail or None)
        return
    try:
        result = (
            client.create(post) if existing is None else client.update(int(existing["id"]), post)
        )
    except SiteError as error:
        if error.reason not in ("unreachable", "timeout", "server_error"):
            finish(State.FAILED, error.reason, None, error.detail or None)
            return
        # The site may have done it before failing to answer: look for the marker (ADR-0026 §2).
        for _ in range(2):
            sleep(RECONCILE_WAIT_SECONDS)
            try:
                found = client.find(publication.marker)
            except SiteError:
                continue
            if len(found) == 1 and has_marker(
                str(found[0].get("raw_content") or ""), publication.marker
            ):
                if str(found[0].get("status")) == post.status:
                    finish(State.DONE, None, found[0], "confirmed after a failure")
                    return
            if len(found) > 1:
                finish(State.TO_CHECK, "several_posts", None, error.detail or None)
                return
        finish(State.FAILED, error.reason, None, error.detail or None)
        return
    finish(State.DONE, None, result, None)


def _slug(status: str, existing: dict[str, Any] | None, marker: str) -> str | None:
    """The slug to send: the key for a new draft, empty to drop the key on publication, none to
    leave it as it is."""
    if existing is None:
        return marker_slug(marker) if status == "draft" else None
    if status == "publish" and existing.get("slug") == marker_slug(marker):
        return ""
    return None
