# SPDX-License-Identifier: AGPL-3.0-or-later
"""The two adapters against a local fake provider, and the SSRF protection of their client
(F05, ADR-0027 §1, §4)."""

import ipaddress
import json
import threading
from collections import deque
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from otlet.ai.adapters.providers import adapter_for
from otlet.ai.domain.model import AiError, Catalogue, Completion, Message, Protocol
from otlet.platform.http import AddressPolicy

SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}


class Fake:
    """Answers the OpenAI and Anthropic protocols; each request takes the next behaviour."""

    def __init__(self) -> None:
        self.behaviours: deque[str] = deque()
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
                elif behaviour in ("500", "400"):
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
                                    "message": {"role": "assistant", "content": '{"title": "T"}'},
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


@pytest.fixture
def fake() -> Iterator[Fake]:
    server = Fake()
    yield server
    server.server.shutdown()


def model(protocol: str) -> Any:
    structured = "tool" if protocol == "anthropic" else "json_schema"
    data = {
        "provider": "local",
        "protocol": protocol,
        "model": "m1",
        "structured_output": structured,
        "context": 1000,
        "price_in": 0,
        "price_out": 0,
        "status": "untested",
        "paid": False,
    }
    return Catalogue.of({"models": [data]}).entries[0]


def call(fake: Fake, protocol: str, endpoint: str | None = None) -> Completion:
    suffix = "/v1" if protocol == "openai" else ""
    return Completion(
        endpoint=endpoint or f"http://127.0.0.1:{fake.port}{suffix}",
        api_key="secret-key",
        model=model(protocol),
        messages=(Message("system", "Answer in JSON."), Message("user", "Hello")),
        schema=SCHEMA,
        schema_name="answer",
        max_output_tokens=100,
        timeout_seconds=5,
    )


def local_policy(fake: Fake) -> AddressPolicy:
    return AddressPolicy(
        allowed_networks=(ipaddress.ip_network("127.0.0.0/8"),),
        allowed_ports=frozenset({80, 443, fake.port}),
    )


@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
def test_a_structured_answer_comes_back_with_its_usage(fake: Fake, protocol: str) -> None:
    answer = adapter_for(Protocol(protocol), local_policy(fake)).complete(call(fake, protocol))
    assert json.loads(answer.text) == {"title": "T"}
    assert (answer.tokens_in, answer.tokens_out) == ((11, 7) if protocol == "openai" else (13, 5))
    sent = fake.requests[-1]["body"]
    if protocol == "openai":
        assert sent["response_format"]["json_schema"]["schema"] == SCHEMA
        assert sent["messages"][0] == {"role": "system", "content": "Answer in JSON."}
    else:
        assert sent["tool_choice"] == {"type": "tool", "name": "answer"}
        assert sent["system"] == "Answer in JSON."
    assert len(fake.requests) == 1  # the SDK does not retry on its own


@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
@pytest.mark.parametrize(
    ("behaviour", "kind"), [("429", "quota"), ("500", "unavailable"), ("400", "refused")]
)
def test_errors_are_normalized_without_retry(
    fake: Fake, protocol: str, behaviour: str, kind: str
) -> None:
    fake.behaviours.append(behaviour)
    with pytest.raises(AiError) as caught:
        adapter_for(Protocol(protocol), local_policy(fake)).complete(call(fake, protocol))
    assert caught.value.kind == kind
    if kind == "quota":
        assert caught.value.retry_after == 1.5
    assert len(fake.requests) == 1


def test_an_internal_address_is_refused_unless_the_administrator_allows_it(fake: Fake) -> None:
    allowed_port_only = AddressPolicy(allowed_ports=frozenset({80, 443, fake.port}))
    with pytest.raises(AiError) as caught:
        adapter_for(Protocol.OPENAI, allowed_port_only).complete(call(fake, "openai"))
    assert (caught.value.kind, caught.value.detail) == ("unavailable", "address_not_allowed")
    # The network is allowed, but not the port.
    network_only = AddressPolicy(allowed_networks=(ipaddress.ip_network("127.0.0.0/8"),))
    with pytest.raises(AiError) as caught:
        adapter_for(Protocol.OPENAI, network_only).complete(call(fake, "openai"))
    assert caught.value.detail == "address_not_allowed"
    assert fake.requests == []
