# SPDX-License-Identifier: AGPL-3.0-or-later
"""S4: deterministic test provider (docs/spikes/S4.md §3.1).

    python fake_provider.py

Port 8001 and 8002: two independent instances of the OpenAI-compatible protocol
(POST /v1/chat/completions), used as fake-a and fake-b. Port 8003: the Anthropic protocol
(POST /v1/messages), answering with a forced tool call.

Each instance has a queue of behaviours, filled by POST /control {"queue": [...]}; every
request takes the next one, "ok" when the queue is empty:
  ok, invalid (broken JSON), 429:<seconds> (Retry-After), 500, 400, timeout (sleeps 6 s).
"ok" answers a valid draft citing the source ids found in the request, with a usage drawn
by a fixed seed: input tokens from 0.8 to 1.3 times characters / 3.5, output tokens from 300
to 1 200, and in 5 % of the answers 1 500 (beyond the maximum asked), to test the margin.
"""

from __future__ import annotations

import json
import random
import re
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PORTS = {8001: "openai", 8002: "openai", 8003: "anthropic"}


class Instance:
    def __init__(self, port: int) -> None:
        self.queue: deque[str] = deque()
        self.lock = threading.Lock()
        self.rng = random.Random(port)
        self.requests = 0

    def next(self) -> tuple[str, float, float, int]:
        with self.lock:
            self.requests += 1
            behaviour = self.queue.popleft() if self.queue else "ok"
            ratio = self.rng.uniform(0.8, 1.3)
            out = 1500 if self.rng.random() < 0.05 else self.rng.randint(300, 1200)
            latency = self.rng.uniform(0.05, 0.3)
        return behaviour, ratio, latency, out


def draft_for(text: str) -> dict[str, Any]:
    ids = sorted(set(re.findall(r"\[(S\d)\]", text))) or ["S1"]
    paragraph = {"text": "Paragraphe de test rédigé par le faux fournisseur.", "source_ids": ids[:2]}
    return {"title": "Titre de test", "lead": "Chapeau de test du faux fournisseur.",
            "sections": [{"heading": "Première partie", "paragraphs": [paragraph]}, {"heading": "Seconde partie", "paragraphs": [paragraph]}],
            "sources_used": ids}


def handler(port: int, instance: Instance) -> type[BaseHTTPRequestHandler]:
    protocol = PORTS[port]

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: object) -> None:
            pass

        def reply(self, status: int, body: Any, headers: dict[str, str] | None = None) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            self.reply(200, {"requests": instance.requests, "queued": list(instance.queue)})

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if self.path == "/control":
                with instance.lock:
                    instance.queue = deque(body.get("queue", []))
                    instance.requests = 0
                self.reply(200, {"queued": len(instance.queue)})
                return
            behaviour, ratio, latency, out = instance.next()
            time.sleep(latency)
            text = json.dumps(body.get("messages", [])) + str(body.get("system", ""))
            tokens_in = int(len(text) / 3.5 * ratio)
            if behaviour.startswith("429"):
                self.reply(429, {"error": {"type": "rate_limit_error", "message": "slow down"}}, {"Retry-After": behaviour.split(":")[1] if ":" in behaviour else "1"})
                return
            if behaviour in ("500", "400"):
                self.reply(int(behaviour), {"error": {"type": "api_error", "message": behaviour}})
                return
            if behaviour == "timeout":
                time.sleep(6)
            content = "{not json" if behaviour == "invalid" else json.dumps(draft_for(text))
            if protocol == "openai":
                self.reply(200, {"id": "fake", "object": "chat.completion", "created": int(time.time()), "model": body.get("model"),
                                 "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
                                 "usage": {"prompt_tokens": tokens_in, "completion_tokens": out, "total_tokens": tokens_in + out}})
            else:
                block = {"type": "tool_use", "id": "toolu_fake", "name": "article_draft", "input": json.loads(content) if behaviour != "invalid" else {"broken": True}}
                self.reply(200, {"id": "msg_fake", "type": "message", "role": "assistant", "model": body.get("model"), "content": [block],
                                 "stop_reason": "tool_use", "stop_sequence": None, "usage": {"input_tokens": tokens_in, "output_tokens": out}})

    return Handler


def main() -> None:
    for port in PORTS:
        server = ThreadingHTTPServer(("0.0.0.0", port), handler(port, Instance(port)))  # noqa: S104 (test network)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print("fake providers listening", list(PORTS), flush=True)
    threading.Event().wait()


if __name__ == "__main__":
    main()
