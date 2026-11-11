# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sites and publications (U07, docs/design/PUBLICATION_WORDPRESS.md, ADR-0026).

A site is a WordPress of the workspace, reached with an application password. A publication ties
one article to one site: the post it became there, its status, the version of Otlet it holds.
Every send goes through `plan`, which says what WordPress must do, or why it must not.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

NAME_MAX = 80
URL_MAX = 300
USERNAME_MAX = 120
PASSWORD_MAX = 200
TERMS_MAX = 20  # categories, and tags, given to one post
TAG_MAX = 60


class PublishingError(Exception):
    """A rule was not met; `code` is stable and translated by the interface."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class Action(StrEnum):
    DRAFT = "draft"  # « Envoyer en brouillon »: the default action
    PUBLISH = "publish"  # « Publier »: separate, confirmed by the author


class State(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    TO_CHECK = "to_check"  # a send whose outcome the site could not confirm (ADR-0026 §2)


@dataclass(frozen=True, slots=True)
class Term:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class Site:
    id: UUID
    workspace_id: UUID
    name: str
    url: str
    username: str
    password_hint: str
    check_result: str | None = None
    check_detail: str | None = None
    check_role: str | None = None
    checked_at: datetime | None = None
    check_pending: bool = False
    categories: tuple[Term, ...] = ()
    tags: tuple[Term, ...] = ()


@dataclass(frozen=True, slots=True)
class Publication:
    id: UUID
    workspace_id: UUID
    article_id: UUID
    site_id: UUID
    marker: str
    action: Action
    asked_version: int
    state: State
    remote_id: int | None = None
    remote_status: str | None = None
    remote_url: str | None = None
    version: int | None = None
    sent_at: datetime | None = None
    error: str | None = None
    categories: tuple[int, ...] = ()
    tags: tuple[str, ...] = ()
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Event:
    at: datetime | None  # None until the store records it
    action: str
    version: int
    result: str
    detail: str | None = None
    remote_status: str | None = None
    user_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class Post:
    """What goes to WordPress for one send."""

    title: str
    content: str
    status: str  # draft or publish
    slug: str | None
    categories: tuple[int, ...] = ()
    tags: tuple[int, ...] = ()  # the ids of the site's tags


def check_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not 1 <= len(cleaned) <= NAME_MAX:
        raise PublishingError("invalid_name", f"a name has 1 to {NAME_MAX} characters")
    return cleaned


def check_url(url: str) -> str:
    """The address of the site, as its visitors type it: http(s), a host, maybe a path."""
    cleaned = url.strip().rstrip("/")
    parts = urlsplit(cleaned)
    if (
        len(cleaned) > URL_MAX
        or parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise PublishingError("invalid_url", "an address starts with http:// or https://")
    return cleaned


def check_username(username: str) -> str:
    cleaned = username.strip()
    if not 1 <= len(cleaned) <= USERNAME_MAX:
        raise PublishingError("invalid_username", "a user name is required")
    return cleaned


def check_password(password: str) -> str:
    """An application password of WordPress: 24 characters, often shown in groups of four."""
    cleaned = "".join(password.split())
    if not 8 <= len(cleaned) <= PASSWORD_MAX:
        raise PublishingError("invalid_password", "an application password is required")
    return cleaned


def password_hint(password: str) -> str:
    return password[-4:]


def check_terms(categories: list[int], tags: list[str]) -> tuple[tuple[int, ...], tuple[str, ...]]:
    if len(categories) > TERMS_MAX or len(tags) > TERMS_MAX:
        raise PublishingError("too_many_terms", f"at most {TERMS_MAX} categories and tags")
    cleaned: list[str] = []
    for tag in tags:
        name = " ".join(tag.split())
        if not 1 <= len(name) <= TAG_MAX:
            raise PublishingError("invalid_tag", f"a tag has 1 to {TAG_MAX} characters")
        if name.lower() not in (t.lower() for t in cleaned):
            cleaned.append(name)
    return tuple(dict.fromkeys(categories)), tuple(cleaned)


def plan(action: Action, remote_status: str | None) -> str:
    """The status the post gets in WordPress for `action`, given its status there now (None: no
    post yet). Otlet never takes an article off line by itself: a draft over a published post
    is refused (Joël, 2026-11-11)."""
    if action is Action.PUBLISH:
        return "publish"
    if remote_status in ("publish", "future", "private"):
        raise PublishingError(
            "already_published",
            "this article is on line: publish the update, or unpublish it in WordPress",
        )
    return "draft"


def marker_slug(marker: str) -> str:
    """The slug that carries the key of ADR-0026 while the post is a draft."""
    return f"otlet-{marker}"


def marker_comment(marker: str) -> str:
    """The HTML comment that carries the key in the content, whatever the slug becomes."""
    return f"<!-- otlet:{marker} -->"


_MARKER = re.compile(r"<!-- otlet:([0-9a-f-]{8,64}) -->")


def has_marker(content: str, marker: str) -> bool:
    return any(found == marker for found in _MARKER.findall(content or ""))
