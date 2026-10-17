# SPDX-License-Identifier: AGPL-3.0-or-later
"""The two adapters of the gateway, on the official SDKs (ADR-0027 §1, TC-08).

- OpenAI protocol (`openai` SDK with a base URL): Ollama, Groq, OpenRouter, OpenAI and any
  compatible server; the structured output goes through `response_format` with a JSON Schema.
- Anthropic protocol (`anthropic` SDK): the structured output goes through a forced tool.

Both SDKs are built without retries of their own (`max_retries=0`): the gateway decides. They
reach providers through the platform's guarded HTTP client, so that an address entered by a
user cannot lead the server into its internal network (SSRF); the administrator may allow a
local engine (Ollama on the network) with an `AddressPolicy`. No other module may import a
provider SDK (import contract).
"""

import ipaddress
import json
from collections.abc import Callable, Mapping
from typing import Any, cast

import anthropic
import openai

from otlet.ai.application.ports import Adapter
from otlet.ai.domain.model import AiError, Answer, Completion, ModelEntry, Protocol
from otlet.ai.domain.settings import InstancePolicy
from otlet.platform.http import DEFAULT_PORTS, AddressPolicy, BlockedAddressError
from otlet.platform.sdk_http import guarded_sdk_client, refused


def _retry_after(headers: Mapping[str, str]) -> float | None:
    try:
        return float(headers.get("retry-after", ""))
    except ValueError:
        return None


def _status_error(status: int, detail: str) -> AiError:
    # 5xx: the provider may come back; 404: no such model or address there, another model of
    # the profile may answer; any other 4xx: the request itself is wrong, no retry.
    kind = "unavailable" if status >= 500 or status == 404 else "refused"
    return AiError(kind, f"HTTP {status} {detail}"[:200])


class OpenAICompatible:
    def __init__(self, policy: AddressPolicy) -> None:
        self._policy = policy

    def complete(self, call: Completion) -> Answer:
        client = openai.OpenAI(
            base_url=call.endpoint,
            api_key=call.api_key or "none",
            max_retries=0,
            timeout=call.timeout_seconds,
            http_client=guarded_sdk_client(self._policy, call.timeout_seconds),
        )
        try:
            response = client.chat.completions.create(
                model=call.model.model,
                # The SDK types its parameters as TypedDicts: plain dicts are what it sends.
                messages=cast(Any, [{"role": m.role, "content": m.content} for m in call.messages]),
                max_tokens=call.max_output_tokens,
                temperature=0.2,
                response_format=cast(
                    Any,
                    {
                        "type": "json_schema",
                        "json_schema": {"name": call.schema_name, "schema": dict(call.schema)},
                    },
                ),
            )
        except BlockedAddressError as error:
            raise AiError("unavailable", "address_not_allowed") from error
        except openai.RateLimitError as error:
            raise AiError("quota", "HTTP 429", _retry_after(error.response.headers)) from error
        except openai.APITimeoutError as error:
            raise AiError("unavailable", "timeout") from error
        except openai.APIConnectionError as error:
            raise AiError("unavailable", _connection_detail(error)) from error
        except openai.APIStatusError as error:
            raise _status_error(error.status_code, error.message) from error
        finally:
            client.close()
        usage = response.usage
        text = response.choices[0].message.content if response.choices else None
        return Answer(
            text or "",
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )


class AnthropicNative:
    def __init__(self, policy: AddressPolicy) -> None:
        self._policy = policy

    def complete(self, call: Completion) -> Answer:
        client = anthropic.Anthropic(
            base_url=call.endpoint,
            api_key=call.api_key or "none",
            max_retries=0,
            timeout=call.timeout_seconds,
            http_client=guarded_sdk_client(self._policy, call.timeout_seconds),
        )
        system = "\n\n".join(m.content for m in call.messages if m.role == "system")
        try:
            response = client.messages.create(
                model=call.model.model,
                max_tokens=call.max_output_tokens,
                system=system,
                messages=cast(
                    Any,
                    [
                        {"role": m.role, "content": m.content}
                        for m in call.messages
                        if m.role != "system"
                    ],
                ),
                tools=cast(
                    Any,
                    [
                        {
                            "name": call.schema_name,
                            "description": "The structured answer.",
                            "input_schema": dict(call.schema),
                        }
                    ],
                ),
                tool_choice={"type": "tool", "name": call.schema_name},
            )
        except BlockedAddressError as error:
            raise AiError("unavailable", "address_not_allowed") from error
        except anthropic.RateLimitError as error:
            raise AiError("quota", "HTTP 429", _retry_after(error.response.headers)) from error
        except anthropic.APITimeoutError as error:
            raise AiError("unavailable", "timeout") from error
        except anthropic.APIConnectionError as error:
            raise AiError("unavailable", _connection_detail(error)) from error
        except anthropic.APIStatusError as error:
            raise _status_error(error.status_code, error.message) from error
        finally:
            client.close()
        tool: Any = next((block for block in response.content if block.type == "tool_use"), None)
        text = json.dumps(tool.input) if tool is not None else ""
        return Answer(text, response.usage.input_tokens, response.usage.output_tokens)


def _connection_detail(error: Exception) -> str:
    # The guarded client refuses forbidden destinations before connecting: say so plainly.
    return "address_not_allowed" if refused(error) else "connection"


def adapter_for(protocol: Protocol, policy: AddressPolicy) -> Adapter:
    if protocol is Protocol.ANTHROPIC:
        return AnthropicNative(policy)
    return OpenAICompatible(policy)


def address_policy(policy: InstancePolicy) -> AddressPolicy:
    """Public addresses, plus the internal networks and ports the administrator allowed for a
    local engine (Ollama on the network)."""
    return AddressPolicy(
        allowed_networks=tuple(ipaddress.ip_network(n) for n in policy.local_networks),
        allowed_ports=DEFAULT_PORTS | frozenset(policy.local_ports),
    )


def adapter_factory(policy: InstancePolicy) -> Callable[[ModelEntry], Adapter]:
    addresses = address_policy(policy)
    return lambda model: adapter_for(model.protocol, addresses)
