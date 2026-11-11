# SPDX-License-Identifier: AGPL-3.0-or-later
"""The REST API of WordPress (wp/v2), reached with an application password (U07, ADR-0026).

Every call goes through the guarded client of the platform: the address the user gave is
checked after resolution, internal addresses only where the administrator allowed them (SSRF,
ARCHITECTURE §13.2). No redirect is followed.
"""

import base64
from collections.abc import Sequence
from typing import Any

import httpx2

from otlet.platform.http import AddressPolicy
from otlet.platform.sdk_http import guarded_sdk_client, refused
from otlet.publishing.application.publishing import SiteError
from otlet.publishing.domain.model import Post, Term, marker_slug

TIMEOUT_SECONDS = 30.0
STATUSES = "draft,pending,publish,private,future"
PER_PAGE = 100


class WordPress:
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        policy: AddressPolicy,
        client: httpx2.Client | None = None,
    ) -> None:
        self._base = url.rstrip("/") + "/wp-json/wp/v2"
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
        self._client = client or guarded_sdk_client(policy, TIMEOUT_SECONDS)

    def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(
                method, self._base + path, headers=self._headers, **kwargs
            )
        except httpx2.TimeoutException as error:
            raise SiteError("timeout", str(error)) from error
        except httpx2.HTTPError as error:
            if refused(error):
                raise SiteError("address_not_allowed", str(error)) from error
            raise SiteError("unreachable", str(error)) from error
        if response.status_code in (301, 302, 307, 308):
            raise SiteError("redirected", response.headers.get("location", ""))
        if response.status_code == 404 and method == "GET" and path.startswith("/posts/"):
            return None
        if response.status_code >= 400:
            code, message = "", ""
            try:
                body = response.json()
                code, message = str(body.get("code") or ""), str(body.get("message") or "")
            except ValueError:
                message = response.text[:200]
            if response.status_code == 401:
                # Valid credentials refused with rest_not_logged_in: a security extension, or a
                # server that drops the Authorization header (ADR-0026 §4).
                reason = "not_logged_in" if code == "rest_not_logged_in" else "bad_credentials"
                raise SiteError(reason, message)
            if response.status_code == 403:
                raise SiteError("forbidden", f"{code} {message}".strip())
            if response.status_code == 404:
                raise SiteError("no_rest_api", f"{code} {message}".strip())
            if response.status_code >= 500:
                raise SiteError("server_error", f"{response.status_code} {message}".strip())
            raise SiteError("refused", f"{response.status_code} {code} {message}".strip())
        try:
            return response.json()
        except ValueError as error:
            raise SiteError("not_wordpress", response.text[:200]) from error

    def me(self) -> str:
        body = self._call("GET", "/users/me", params={"context": "edit"})
        roles = body.get("roles") or []
        return str(roles[0]) if roles else ""

    def _terms(self, kind: str) -> list[Term]:
        body = self._call(
            "GET", f"/{kind}", params={"per_page": PER_PAGE, "orderby": "name", "hide_empty": 0}
        )
        return [Term(int(t["id"]), str(t.get("name") or "")) for t in body]

    def categories(self) -> list[Term]:
        return self._terms("categories")

    def tags(self) -> list[Term]:
        return self._terms("tags")

    def tag_ids(self, names: Sequence[str]) -> list[int]:
        """The ids of the tags named, created when the site has none of that name."""
        ids: list[int] = []
        for name in names:
            found = self._call("GET", "/tags", params={"search": name, "per_page": PER_PAGE})
            same = [t for t in found if str(t.get("name") or "").lower() == name.lower()]
            if same:
                ids.append(int(same[0]["id"]))
                continue
            try:
                created = self._call("POST", "/tags", json={"name": name})
            except SiteError as error:
                if error.reason == "forbidden":
                    raise SiteError(
                        "tag_not_allowed",
                        f"the account may not create the tag « {name} »: create it in WordPress",
                    ) from error
                raise
            ids.append(int(created["id"]))
        return ids

    @staticmethod
    def _post(body: dict[str, Any]) -> dict[str, Any]:
        content = body.get("content") or {}
        return {
            "id": body.get("id"),
            "status": body.get("status"),
            "link": body.get("link"),
            "slug": body.get("slug"),
            "raw_content": content.get("raw") if isinstance(content, dict) else "",
        }

    def get(self, post_id: int) -> dict[str, Any] | None:
        body = self._call("GET", f"/posts/{post_id}", params={"context": "edit"})
        return None if body is None else self._post(body)

    def find(self, marker: str) -> list[dict[str, Any]]:
        """The posts that carry the key of an article: by slug (a draft), else by the comment of
        the content (ADR-0026 §1)."""
        params = {"status": STATUSES, "context": "edit", "per_page": 10}
        by_slug = self._call("GET", "/posts", params={**params, "slug": marker_slug(marker)})
        found = {int(p["id"]): self._post(p) for p in by_slug}
        if not found:
            searched = self._call("GET", "/posts", params={**params, "search": marker})
            for p in searched:
                post = self._post(p)
                if f"otlet:{marker}" in str(post["raw_content"] or ""):
                    found[int(p["id"])] = post
        return list(found.values())

    @staticmethod
    def _fields(post: Post) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "title": post.title,
            "content": post.content,
            "status": post.status,
            "categories": list(post.categories),
            "tags": list(post.tags),
        }
        if post.slug is not None:
            fields["slug"] = post.slug
        return fields

    def create(self, post: Post) -> dict[str, Any]:
        return self._post(self._call("POST", "/posts", json=self._fields(post)))

    def update(self, post_id: int, post: Post) -> dict[str, Any]:
        return self._post(self._call("POST", f"/posts/{post_id}", json=self._fields(post)))
