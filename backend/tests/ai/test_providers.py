# SPDX-License-Identifier: AGPL-3.0-or-later
"""The two adapters against a local fake provider, and the SSRF protection of their client
(F05, ADR-0027 §1, §4)."""

import ipaddress
import json
from collections.abc import Iterator
from typing import Any

import pytest

from ai_support import Fake
from otlet.ai.adapters.providers import adapter_for
from otlet.ai.domain.model import AiError, Catalogue, Completion, Message, Protocol
from otlet.platform.http import AddressPolicy

SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}


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
