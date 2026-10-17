# SPDX-License-Identifier: AGPL-3.0-or-later
"""A local fake AI provider for the tests: the OpenAI and Anthropic protocols, scripted."""

import json
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class Fake:
    """Answers the OpenAI and Anthropic protocols; each request takes the next behaviour."""

    def __init__(self) -> None:
        self.behaviours: deque[str] = deque()
        self.answer = '{"title": "T"}'  # the JSON every successful answer carries
        self.requests: list[dict[str, Any]] = []
        fake = self

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

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"path": self.path, "body": body, "auth": self.headers})
                behaviour = fake.behaviours.popleft() if fake.behaviours else "ok"
                if behaviour == "429":
                    self.reply(429, {"error": {"message": "slow"}}, {"Retry-After": "1.5"})
                elif behaviour in ("500", "404", "400"):
                    self.reply(int(behaviour), {"error": {"message": behaviour}})
                elif self.path.endswith("/chat/completions"):
                    self.reply(
                        200,
                        {
                            "id": "x",
                            "object": "chat.completion",
                            "created": 0,
                            "model": body["model"],
                            "choices": [
                                {
                                    "index": 0,
                                    "finish_reason": "stop",
                                    "message": {"role": "assistant", "content": fake.answer},
                                }
                            ],
                            "usage": {
                                "prompt_tokens": 11,
                                "completion_tokens": 7,
                                "total_tokens": 18,
                            },
                        },
                    )
                else:
                    self.reply(
                        200,
                        {
                            "id": "m",
                            "type": "message",
                            "role": "assistant",
                            "model": body["model"],
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "t",
                                    "name": "answer",
                                    "input": {"title": "T"},
                                }
                            ],
                            "stop_reason": "tool_use",
                            "stop_sequence": None,
                            "usage": {"input_tokens": 13, "output_tokens": 5},
                        },
                    )

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
