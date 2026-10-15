# SPDX-License-Identifier: AGPL-3.0-or-later
"""S7.2: checks V1, V2 and V3 of RISKS.md §11.2 (docs/spikes/S7.md §3.2).

    python vchecks.py [--results results]

Runs on the measurement machine, in the CMS network, with ~/otlet-cms.env in the environment.
Every step records the request, the HTTP status and the part of the answer that proves the
point. Writes results/vchecks-<time>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cms
from cms import ALL_STATUSES, Ghost, WordPress, configurations

HERE = Path(__file__).parent
steps: list[dict[str, Any]] = []


def record(check: str, target: str, what: str, status: int, evidence: Any, holds: bool | None = None) -> None:
    steps.append({"check": check, "target": target, "step": what, "status": status, "evidence": evidence, "holds": holds})
    print(f"{check} {target} {what}: {status} {'' if holds is None else holds}")


def ids(body: Any) -> list[int]:
    return [p["id"] for p in body] if isinstance(body, list) else []


# --- V1: WordPress lookup by an arbitrary metadata -----------------------------------------

def v1(wp: WordPress) -> None:
    key = uuid.uuid4().hex
    marker = f"<!-- otlet:{key} -->"
    status, post = wp.api("POST", "posts", {
        "title": f"S7 V1 {key[:8]}", "status": "draft", "slug": f"otlet-{key[:12]}",
        "content": f"{marker}<p>Paragraphe de test.</p>", "meta": {"otlet_key": key},
    })
    record("V1", wp.name, "create draft with meta, slug and HTML comment marker", status, {"id": post.get("id") if isinstance(post, dict) else None, "meta": post.get("meta") if isinstance(post, dict) else post})
    if status != 201:
        return
    post_id = post["id"]
    record("V1", wp.name, "unregistered meta is stored", status, post.get("meta"), holds=not (isinstance(post.get("meta"), dict) and post["meta"].get("otlet_key") == key))

    status, found = wp.api("GET", "posts", status=ALL_STATUSES, meta_key="otlet_key", meta_value=key, per_page=100, context="edit")
    record("V1", wp.name, "filter by meta_key/meta_value", status, {"returned": len(found) if isinstance(found, list) else found, "only_target": ids(found) == [post_id]}, holds=ids(found) != [post_id])

    status, found = wp.api("GET", "posts", status=ALL_STATUSES, slug=f"otlet-{key[:12]}", context="edit")
    record("V1", wp.name, "native lookup by slug (draft)", status, {"ids": ids(found), "slug_kept": isinstance(found, list) and bool(found) and found[0].get("slug") == f"otlet-{key[:12]}"})

    status, found = wp.api("GET", "posts", status=ALL_STATUSES, search=key, context="edit")
    raw_kept = isinstance(found, list) and bool(found) and marker in found[0]["content"]["raw"]
    record("V1", wp.name, "native lookup by search on the HTML comment marker", status, {"ids": ids(found), "marker_in_raw_content": raw_kept})


# --- V2: Ghost custom fields and markers ---------------------------------------------------

def v2(ghost: Ghost) -> None:
    key = uuid.uuid4().hex
    status, body = ghost.api("POST", "posts/", {"posts": [{"title": f"S7 V2 {key[:8]}", "status": "draft", "otlet_key": key}]}, source="html")
    record("V2", ghost.name, "create post with an unknown field", status, body if status >= 400 else {"field_kept": "otlet_key" in body["posts"][0]}, holds=status >= 400 or "otlet_key" not in body["posts"][0])
    if status < 400:
        ghost.api("DELETE", f"posts/{body['posts'][0]['id']}/")

    tag = f"#otlet-{key[:12]}"
    status, body = ghost.api("POST", "posts/", {"posts": [{"title": f"S7 V2 tag {key[:8]}", "status": "draft", "slug": f"otlet-{key[:12]}", "tags": [{"name": tag}], "html": "<p>Test.</p>"}]}, source="html")
    post = body["posts"][0] if status == 201 else {}
    record("V2", ghost.name, "create draft with an internal tag and a slug", status, {"tags": [(t["name"], t["slug"], t["visibility"]) for t in post.get("tags", [])], "slug": post.get("slug")})
    if status != 201:
        return
    tag_slug = post["tags"][0]["slug"]
    status, found = ghost.api("GET", "posts/", filter=f"tag:{tag_slug}+status:[draft,published,scheduled]", limit="all")
    record("V2", ghost.name, "lookup by internal tag", status, {"ids": [p["id"] for p in found.get("posts", [])], "only_target": [p["id"] for p in found.get("posts", [])] == [post["id"]]})
    status, found = ghost.api("GET", "posts/", filter=f"slug:{post['slug']}+status:[draft,published,scheduled]")
    record("V2", ghost.name, "lookup by slug", status, {"ids": [p["id"] for p in found.get("posts", [])]})
    status, read = ghost.api("GET", f"posts/{post['id']}/")
    record("V2", ghost.name, "internal tag hidden from the public site", status, {"visibility": [t["visibility"] for t in read["posts"][0]["tags"]]})


# --- V3: effective rights of the credentials -----------------------------------------------

def v3_wordpress(base: str, label: str, user: str, password: str, other_post: int) -> None:
    wp = WordPress(label, base, user, password)
    status, own = wp.api("POST", "posts", {"title": f"S7 V3 {label}", "status": "draft", "content": "<p>V3</p>"})
    record("V3", label, "create own draft", status, None)
    if status == 201:
        status, _ = wp.api("POST", f"posts/{own['id']}", {"status": "publish"})
        record("V3", label, "publish own post", status, None)
        wp.api("DELETE", f"posts/{own['id']}", force="true")
    for what, method, path, body in (
        ("edit another user's post", "POST", f"posts/{other_post}", {"title": "modifié par V3"}),
        ("list users with emails (context=edit)", "GET", "users?context=edit", None),
        ("create a user", "POST", "users", {"username": f"v3-{uuid.uuid4().hex[:6]}", "email": f"{uuid.uuid4().hex[:6]}@example.org", "password": uuid.uuid4().hex}),
        ("list plugins", "GET", "plugins", None),
        ("read site settings", "GET", "settings", None),
        ("delete another user's post", "DELETE", f"posts/{other_post}", None),
    ):
        status, answer = wp.api(method, path, body)
        code = answer.get("code") if isinstance(answer, dict) else None
        record("V3", label, what, status, code)


def v3_ghost(ghost: Ghost) -> None:
    status, body = ghost.api("POST", "posts/", {"posts": [{"title": "S7 V3 ghost", "status": "published", "html": "<p>V3</p>"}]}, source="html")
    record("V3", ghost.name, "create and publish a post", status, None)
    if status == 201:
        status, _ = ghost.api("DELETE", f"posts/{body['posts'][0]['id']}/")
        record("V3", ghost.name, "delete a post", status, None)
    for what, method, path in (
        ("list staff users", "GET", "users/"),
        ("read settings", "GET", "settings/"),
        ("list members (subscribers)", "GET", "members/"),
        ("list themes", "GET", "themes/"),
        ("list integrations", "GET", "integrations/"),
    ):
        status, answer = ghost.api(method, path)
        record("V3", ghost.name, what, status, answer.get("errors", [{}])[0].get("type") if isinstance(answer, dict) and "errors" in answer else None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(HERE / "results"))
    args = parser.parse_args()
    cms.TIMEOUT = 120.0  # checks, not the fault measure: Ghost is slow on this machine
    targets = configurations()
    for name in ("W1", "W2", "W3"):
        v1(targets[name])  # type: ignore[arg-type]
    # Least privilege: the marker must survive the content filter of an Author (no unfiltered_html).
    v1(WordPress("W1-author", targets["W1"].base, "s7-author", os.environ["WP_AUTHOR_APP_PASSWORD"]))
    v2(targets["G1"])  # type: ignore[arg-type]

    admin = targets["W1"]
    status, other = admin.api("POST", "posts", {"title": "S7 V3 post de l'administrateur", "status": "publish", "content": "<p>Admin.</p>"})
    other_id = other["id"]
    for label, user, variable in (("W1-author", "s7-author", "WP_AUTHOR_APP_PASSWORD"), ("W1-editor", "s7-editor", "WP_EDITOR_APP_PASSWORD"), ("W1-admin", "admin", "WP_APP_PASSWORD")):
        status, alive = admin.api("GET", f"posts/{other_id}", context="edit")
        if status != 200:  # deleted by the previous role: recreate the target
            status, other = admin.api("POST", "posts", {"title": "S7 V3 post de l'administrateur", "status": "publish", "content": "<p>Admin.</p>"})
            other_id = other["id"]
        v3_wordpress(admin.base, label, user, os.environ[variable], other_id)
    v3_ghost(targets["G1"])  # type: ignore[arg-type]

    out = Path(args.results)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"vchecks-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps({"started": steps and datetime.now(UTC).isoformat(timespec="seconds"), "steps": steps}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Result: {path}")


if __name__ == "__main__":
    main()
