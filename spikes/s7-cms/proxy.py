# SPDX-License-Identifier: AGPL-3.0-or-later
"""S7.5: fault-injecting HTTP proxy between the connector and the CMS (docs/spikes/S7.md §3.4).

    python proxy.py

Listens on one port per configuration and forwards to the CMS. A request carrying the header
X-S7-Fault gets that fault; the others pass through unchanged:

- cut_before:    the request is read, then the connection is closed; the CMS never sees it;
- timeout_after: the request is forwarded and answered by the CMS, then the answer is held
                 beyond the connector timeout (10 s) before being sent;
- cut_response:  the request is forwarded and answered by the CMS, then the connection is
                 closed after the first bytes of the answer.

Every request is logged on stdout as one JSON line (time, port, method, path, fault, status).
"""

from __future__ import annotations

import http.client
import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROUTES = {9081: ("wordpress", 80), 9082: ("wordpress-previous", 80), 9083: ("wordpress-secured", 80), 9368: ("ghost", 2368)}
HOLD_SECONDS = 15.0  # beyond the connector timeout of 10 s
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-connection"}
lock = threading.Lock()


def log(**fields: object) -> None:
    with lock:
        print(json.dumps({"t": round(time.time(), 3), **fields}), flush=True)


def handler_for(port: int) -> type[BaseHTTPRequestHandler]:
    host, upstream_port = ROUTES[port]

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: object) -> None:  # replaced by log()
            pass

        def handle_any(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            fault = self.headers.get("X-S7-Fault", "none")
            if fault == "cut_before":
                log(port=port, method=self.command, path=self.path, fault=fault, status=None)
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
                return
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP | {"host", "x-s7-fault", "content-length"}}
            upstream = http.client.HTTPConnection(host, upstream_port, timeout=300)
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            payload = response.read()
            upstream.close()
            log(port=port, method=self.command, path=self.path, fault=fault, status=response.status)
            head = f"HTTP/1.1 {response.status} {response.reason}\r\n"
            for key, value in response.getheaders():
                if key.lower() not in HOP_BY_HOP | {"content-length"}:
                    head += f"{key}: {value}\r\n"
            head += f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n"
            raw = head.encode("latin-1") + payload
            if fault == "timeout_after":
                time.sleep(HOLD_SECONDS)
            if fault == "cut_response":
                self.wfile.write(raw[:20])
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
                return
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the connector gave up (timeout_after)
            self.close_connection = True

        do_GET = do_POST = do_PUT = do_DELETE = handle_any

    return Handler


def main() -> int:
    servers = [ThreadingHTTPServer(("0.0.0.0", port), handler_for(port)) for port in ROUTES]  # noqa: S104 (test network)
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    log(event="listening", ports=list(ROUTES))
    threading.Event().wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
