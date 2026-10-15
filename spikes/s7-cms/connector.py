# SPDX-License-Identifier: AGPL-3.0-or-later
"""S7.3, S7.4: publication state machine with idempotency key and reconciliation.

docs/spikes/S7.md §3.3. One adapter per CMS carries the marker of the idempotency key:

- WordPress: a slug "otlet-<key>" (searchable natively, drafts included, and not made unique
  for drafts, so that a duplicate is visible) plus an HTML comment in the content;
- Ghost: an internal tag "#otlet-<key>" (filterable natively, hidden from the public site).

States: to_send -> sending -> published, or after a network failure:
sending -> uncertain -> (lookup) -> published | absent -> to_send | to_verify.
A resend happens only after two lookups, 5 s apart, both concluding to absence.
"""

from __future__ import annotations

import http.client
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from cms import ALL_STATUSES, Ghost, WordPress

GRACE_SECONDS = 5.0
MAX_ATTEMPTS = 3
HEURISTIC_WINDOW = timedelta(minutes=10)
NETWORK_ERRORS = (OSError, http.client.HTTPException)


def marker(key: str) -> str:
    return f"otlet-{key[:12]}"


class Adapter(Protocol):
    name: str

    def create(self, title: str, html: str, key: str, fault: str | None) -> tuple[int, str | None]: ...
    def exists(self, remote_id: str) -> bool: ...
    def find_by_marker(self, key: str) -> list[str]: ...
    def find_by_title(self, title: str, since: datetime) -> list[str]: ...
    def inventory(self) -> list[dict[str, Any]]: ...
    def purge(self) -> int: ...


@dataclass
class WordPressAdapter:
    wp: WordPress

    @property
    def name(self) -> str:
        return self.wp.name

    def create(self, title: str, html: str, key: str, fault: str | None) -> tuple[int, str | None]:
        body = {"title": title, "status": "draft", "slug": marker(key), "content": f"<!-- otlet:{key} -->{html}"}
        status, post = self.wp.api("POST", "posts", body, fault=fault)
        return status, str(post["id"]) if status == 201 and isinstance(post, dict) and "id" in post else None

    def exists(self, remote_id: str) -> bool:
        status, _ = self.wp.api("GET", f"posts/{remote_id}", context="edit")
        return status == 200

    def find_by_marker(self, key: str) -> list[str]:
        status, found = self.wp.api("GET", "posts", status=ALL_STATUSES, slug=marker(key), context="edit", per_page=100)
        if status != 200:
            raise OSError(f"lookup refused: HTTP {status}")
        return [str(p["id"]) for p in found]

    def find_by_title(self, title: str, since: datetime) -> list[str]:
        status, found = self.wp.api("GET", "posts", status=ALL_STATUSES, search=title, context="edit", per_page=100)
        if status != 200:
            raise OSError(f"lookup refused: HTTP {status}")
        return [
            str(p["id"]) for p in found
            if p["title"]["raw"] == title and datetime.fromisoformat(p["date_gmt"]).replace(tzinfo=UTC) >= since - HEURISTIC_WINDOW
        ]

    def inventory(self) -> list[dict[str, Any]]:
        posts, page = [], 1
        while True:
            status, found = self.wp.api("GET", "posts", status=ALL_STATUSES, context="edit", per_page=100, page=page)
            if status != 200 or not found:
                return posts
            posts += [{"id": str(p["id"]), "title": p["title"]["raw"], "marker": p["slug"]} for p in found]
            page += 1

    def purge(self) -> int:
        count = 0
        for post in self.inventory():
            self.wp.api("DELETE", f"posts/{post['id']}", force="true")
            count += 1
        return count


@dataclass
class GhostAdapter:
    ghost: Ghost

    @property
    def name(self) -> str:
        return self.ghost.name

    def create(self, title: str, html: str, key: str, fault: str | None) -> tuple[int, str | None]:
        body = {"posts": [{"title": title, "status": "draft", "slug": marker(key), "tags": [{"name": f"#{marker(key)}"}], "html": html}]}
        status, created = self.ghost.api("POST", "posts/", body, fault=fault, source="html")
        return status, created["posts"][0]["id"] if status == 201 and isinstance(created, dict) and created.get("posts") else None

    def exists(self, remote_id: str) -> bool:
        status, _ = self.ghost.api("GET", f"posts/{remote_id}/")
        return status == 200

    def find_by_marker(self, key: str) -> list[str]:
        status, found = self.ghost.api("GET", "posts/", filter=f"tag:hash-{marker(key)}", limit="all", fields="id")
        if status != 200:
            raise OSError(f"lookup refused: HTTP {status}")
        return [p["id"] for p in found["posts"]]

    def find_by_title(self, title: str, since: datetime) -> list[str]:
        status, found = self.ghost.api("GET", "posts/", limit=50, order="created_at desc", fields="id,title,created_at")
        if status != 200:
            raise OSError(f"lookup refused: HTTP {status}")
        return [
            p["id"] for p in found["posts"]
            if p["title"] == title and datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) >= since - HEURISTIC_WINDOW
        ]

    def inventory(self) -> list[dict[str, Any]]:
        status, found = self.ghost.api("GET", "posts/", limit="all", include="tags")
        if status != 200:
            return []
        return [
            {"id": p["id"], "title": p["title"], "marker": next((t["name"][1:] for t in p.get("tags", []) if t["name"].startswith("#otlet-")), None)}
            for p in found["posts"]
        ]

    def purge(self) -> int:
        count = 0
        for post in self.inventory():
            self.ghost.api("DELETE", f"posts/{post['id']}/")
            count += 1
        return count


def adapter(target: WordPress | Ghost) -> Adapter:
    return WordPressAdapter(target) if isinstance(target, WordPress) else GhostAdapter(target)


@dataclass
class Publication:
    title: str
    html: str
    key: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: str = "to_send"
    remote_id: str | None = None
    how: str | None = None  # direct, marker, heuristic
    events: list[dict[str, Any]] = field(default_factory=list)
    resends: list[dict[str, Any]] = field(default_factory=list)

    def event(self, kind: str, **data: Any) -> None:
        self.events.append({"t": round(time.time(), 3), "event": kind, **data})


def publish(target: Adapter, publication: Publication, first_fault: str | None = None) -> Publication:
    started = datetime.now(UTC)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        publication.state = "sending"
        fault = first_fault if attempt == 1 else None
        try:
            status, remote_id = target.create(publication.title, publication.html, publication.key, fault)
        except NETWORK_ERRORS as error:
            publication.event("send_failed", attempt=attempt, fault=fault, error=type(error).__name__)
            publication.state = "uncertain"
        else:
            publication.event("sent", attempt=attempt, fault=fault, status=status)
            if remote_id and target.exists(remote_id):
                publication.state, publication.remote_id, publication.how = "published", remote_id, "direct"
                return publication
            if 400 <= status < 500:  # refused by the CMS: nothing was created
                publication.state = "refused"
                return publication
            publication.state = "uncertain"  # 5xx, or created but not readable

        # uncertain: look for the marker twice, GRACE_SECONDS apart
        lookups: list[Any] = []
        for _ in range(2):
            time.sleep(GRACE_SECONDS)
            try:
                found = target.find_by_marker(publication.key)
            except NETWORK_ERRORS as error:
                lookups.append(f"error: {error}")
                continue
            lookups.append(found)
            if len(found) == 1:
                publication.event("reconciled", how="marker", lookups=lookups)
                publication.state, publication.remote_id, publication.how = "published", found[0], "marker"
                return publication
            if len(found) > 1:
                publication.event("duplicate_seen", lookups=lookups)
                publication.state = "to_verify"
                return publication
        if all(lookup == [] for lookup in lookups):
            publication.event("absent", lookups=lookups)
            publication.resends.append({"attempt": attempt + 1, "lookups": lookups})
            publication.state = "to_send"
            continue
        # the marker lookup could not conclude: heuristic fallback, exactly one candidate
        try:
            candidates = target.find_by_title(publication.title, started)
        except NETWORK_ERRORS as error:
            candidates = [f"error: {error}"]
        publication.event("heuristic", lookups=lookups, candidates=candidates)
        if len(candidates) == 1 and not str(candidates[0]).startswith("error"):
            publication.state, publication.remote_id, publication.how = "published", candidates[0], "heuristic"
        else:
            publication.state = "to_verify"
        return publication
    publication.state = "to_verify"
    publication.event("max_attempts")
    return publication
