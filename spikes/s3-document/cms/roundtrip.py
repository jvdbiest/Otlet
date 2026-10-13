# SPDX-License-Identifier: AGPL-3.0-or-later
"""S3.6, criteria C1 and C2: round trip of the corpus through WordPress and Ghost.

    python roundtrip.py setup-ghost        owner, then an integration; prints its Admin API key
    python roundtrip.py run                publishes every document as a draft, reads it back

Environment: WP_URL, WP_USER, WP_APP_PASSWORD (WordPress current), WP_PREVIOUS_URL,
WP_PREVIOUS_APP_PASSWORD (optional, informative), GHOST_URL, GHOST_ADMIN_KEY ("id:secret"),
GHOST_EMAIL, GHOST_PASSWORD (setup only). Standard library only.

Each document is rendered by otlet_doc.render (with mention and Sources), sent as HTML,
read back as rendered by the CMS, and its mandatory elements extracted (otlet_doc.extract)
and compared with corpus/expected.json. Writes results/roundtrip-<time>.json.
"""

from __future__ import annotations

import base64
import collections
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from otlet_doc import extract, render  # noqa: E402
from selfcheck import load  # noqa: E402

ELEMENTS = ("headings", "links", "citations", "sources", "mention_ia")


def request(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=60) as response:  # noqa: S310 (local test CMS)
        payload = response.read()
        return json.loads(payload) if payload else None


# --- WordPress -----------------------------------------------------------------------------

def wordpress_roundtrip(base: str, user: str, password: str, title: str, html: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    auth = {"Authorization": f"Basic {token}"}
    post = request("POST", f"{base}/wp-json/wp/v2/posts", {"title": title, "content": html, "status": "draft"}, auth)
    read = request("GET", f"{base}/wp-json/wp/v2/posts/{post['id']}?context=edit", headers=auth)
    return str(read["content"]["rendered"])


# --- Ghost ---------------------------------------------------------------------------------

def ghost_token(key: str) -> str:
    key_id, secret = key.split(":")
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    now = int(time.time())
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": key_id}).encode())
    payload = b64(json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}).encode())
    signature = hmac.new(bytes.fromhex(secret), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{b64(signature)}"


def ghost_roundtrip(base: str, key: str, title: str, html: str) -> str:
    auth = {"Authorization": f"Ghost {ghost_token(key)}", "Accept-Version": "v6.0"}
    created = request("POST", f"{base}/ghost/api/admin/posts/?source=html", {"posts": [{"title": title, "html": html, "status": "draft"}]}, auth)
    post_id = created["posts"][0]["id"]
    read = request("GET", f"{base}/ghost/api/admin/posts/{post_id}/?formats=html", headers=auth)
    return str(read["posts"][0]["html"] or "")


def setup_ghost() -> None:
    base = os.environ["GHOST_URL"]
    email, password = os.environ["GHOST_EMAIL"], os.environ["GHOST_PASSWORD"]
    origin = {"Origin": base, "Accept-Version": "v6.0"}
    request("POST", f"{base}/ghost/api/admin/authentication/setup/", {"setup": [{"name": "S3", "email": email, "password": password, "blogTitle": "S3"}]}, origin)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    session = urllib.request.Request(f"{base}/ghost/api/admin/session/", data=json.dumps({"username": email, "password": password}).encode(), method="POST")
    for header, value in {**origin, "Content-Type": "application/json"}.items():
        session.add_header(header, value)
    opener.open(session, timeout=60)
    integration = urllib.request.Request(f"{base}/ghost/api/admin/integrations/?include=api_keys", data=json.dumps({"integrations": [{"name": "otlet-s3"}]}).encode(), method="POST")
    for header, value in {**origin, "Content-Type": "application/json"}.items():
        integration.add_header(header, value)
    payload = json.loads(opener.open(integration, timeout=60).read())
    admin = next(k for k in payload["integrations"][0]["api_keys"] if k["type"] == "admin")
    print(f"{admin['id']}:{admin['secret']}")


# --- comparison ----------------------------------------------------------------------------

def compare(found: dict[str, Any], wanted: dict[str, Any]) -> dict[str, list[int]]:
    """Per element: [found, expected], as multisets of normalized items."""
    result: dict[str, list[int]] = {}
    for element in ELEMENTS:
        if element == "mention_ia":
            if wanted[element]:
                result[element] = [1 if found[element] else 0, 1]
            continue
        want = collections.Counter(json.dumps(item, sort_keys=True, ensure_ascii=False) for item in wanted[element])
        got = collections.Counter(json.dumps(item, sort_keys=True, ensure_ascii=False) for item in found[element])
        result[element] = [sum((want & got).values()), sum(want.values())]
    return result


def run() -> None:
    expected = json.loads((ROOT / "corpus" / "expected.json").read_text(encoding="utf-8"))
    targets = {
        "wordpress": lambda t, h: wordpress_roundtrip(os.environ["WP_URL"], os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"], t, h),
        "ghost": lambda t, h: ghost_roundtrip(os.environ["GHOST_URL"], os.environ["GHOST_ADMIN_KEY"], t, h),
    }
    if os.environ.get("WP_PREVIOUS_APP_PASSWORD"):
        targets["wordpress_previous"] = lambda t, h: wordpress_roundtrip(os.environ["WP_PREVIOUS_URL"], os.environ["WP_USER"], os.environ["WP_PREVIOUS_APP_PASSWORD"], t, h)
    report: dict[str, Any] = {"criteria": "C1 C2", "started": datetime.now(UTC).isoformat(timespec="seconds"), "targets": {}}
    for target, publish in targets.items():
        totals: dict[str, list[int]] = {e: [0, 0] for e in ELEMENTS}
        failures = []
        for name, wanted in expected.items():
            html = render.render(load(name))
            try:
                returned = publish(f"S3 {name}", html)
            except urllib.error.HTTPError as error:
                failures.append({"document": name, "error": f"HTTP {error.code}: {error.read()[:300]!r}"})
                continue
            scores = compare(extract.extract(returned), wanted)
            for element, (got, want) in scores.items():
                totals[element][0] += got
                totals[element][1] += want
            lost = {e: s for e, s in scores.items() if s[0] != s[1]}
            if lost:
                failures.append({"document": name, "lost": lost, "returned_excerpt": returned[:1500]})
        report["targets"][target] = {
            "conservation": {e: {"found": f, "expected": w, "rate": round(f / w, 4) if w else None} for e, (f, w) in totals.items()},
            "documents_fully_conserved": len(expected) - len(failures),
            "failures": failures,
        }
        print(target, json.dumps({e: f"{f}/{w}" for e, (f, w) in totals.items()}), f"{len(expected) - len(failures)}/{len(expected)} documents")
    (ROOT / "results").mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = ROOT / "results" / f"roundtrip-{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Result: {path}")


if __name__ == "__main__":
    {"setup-ghost": setup_ghost, "run": run}[sys.argv[1]]()
