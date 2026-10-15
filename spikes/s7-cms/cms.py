# SPDX-License-Identifier: AGPL-3.0-or-later
"""S7: minimal HTTP clients for the WordPress REST API and the Ghost Admin API.

Standard library only. Every call returns (status, body) and never raises on an HTTP error
status, so that the checks can record refusals as evidence. Network failures (timeouts,
cuts) do raise: the connector turns them into the "uncertain" state.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

TIMEOUT = 10.0  # connector timeout, docs/spikes/S7.md §3.4


def call(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None, timeout: float | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as response:  # noqa: S310 (local test CMS)
            payload = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        payload, status = error.read(), error.code
    try:
        return status, json.loads(payload) if payload else None
    except ValueError:
        return status, payload[:300].decode(errors="replace")


def with_fault(headers: dict[str, str], fault: str | None) -> dict[str, str]:
    """Asks the fault proxy (proxy.py) for a fault on this request."""
    return {**headers, "X-S7-Fault": fault} if fault else headers


@dataclass(frozen=True)
class WordPress:
    name: str
    base: str
    user: str
    password: str

    def headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    def api(self, method: str, path: str, body: Any = None, fault: str | None = None, **params: Any) -> tuple[int, Any]:
        query = f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""
        return call(method, f"{self.base}/wp-json/wp/v2/{path}{query}", body, with_fault(self.headers(), fault))


@dataclass(frozen=True)
class Ghost:
    name: str
    base: str
    key: str  # "id:secret"

    def headers(self) -> dict[str, str]:
        key_id, secret = self.key.split(":")[-2:]

        def b64(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        now = int(time.time())
        header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": key_id}).encode())
        payload = b64(json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}).encode())
        signature = hmac.new(bytes.fromhex(secret), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        return {"Authorization": f"Ghost {header}.{payload}.{b64(signature)}", "Accept-Version": "v6.0"}

    def api(self, method: str, path: str, body: Any = None, fault: str | None = None, **params: Any) -> tuple[int, Any]:
        query = f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""
        return call(method, f"{self.base}/ghost/api/admin/{path}{query}", body, with_fault(self.headers(), fault))


ALL_STATUSES = "draft,pending,private,publish,future"


def configurations(proxy: str | None = None) -> dict[str, WordPress | Ghost]:
    """The four configurations of docs/spikes/S7.md §3.1, optionally through the fault proxy."""
    env = os.environ

    def url(direct: str, port: int) -> str:
        return f"{proxy}:{port}" if proxy else direct

    return {
        "W1": WordPress("W1", url("http://wordpress", 9081), "admin", env["WP_APP_PASSWORD"]),
        "W2": WordPress("W2", url("http://wordpress-previous", 9082), "admin", env["WP_PREVIOUS_APP_PASSWORD"]),
        "W3": WordPress("W3", url("http://wordpress-secured", 9083), "admin", env["WP_SECURED_APP_PASSWORD"]),
        "G1": Ghost("G1", url("http://ghost:2368", 9368), env["GHOST_ADMIN_KEY"]),
    }
