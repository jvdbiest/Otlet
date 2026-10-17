# SPDX-License-Identifier: AGPL-3.0-or-later
"""The models an instance knows, their status, and the cost of a call (ADR-0027 §2, §3).

The catalogue is versioned data: for each model, the protocol of its provider, how it gives a
structured output, its prices and its status. A model is « testé » when it held criterion C1
of S4 on the 50 briefs, « non testé » when it may be used with a warning, « bloqué » when the
gateway refuses it before any call. A paid provider is blocked until the administrator of the
instance allows it; the user then chooses, among what is allowed, the providers and models of
their own profile.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

# Input tokens are estimated from characters, with a margin (S4: up to 1.3 times the estimate).
CHARACTERS_PER_TOKEN = Decimal("3.5")
INPUT_MARGIN = Decimal("1.2")
PER_MILLION = Decimal(1_000_000)


class Protocol(StrEnum):
    OPENAI = "openai"  # the OpenAI chat completions API, spoken by Ollama, Groq, OpenRouter…
    ANTHROPIC = "anthropic"


class Status(StrEnum):
    TESTED = "tested"
    UNTESTED = "untested"
    BLOCKED = "blocked"


class StructuredOutput(StrEnum):
    JSON_SCHEMA = "json_schema"  # response_format of the OpenAI protocol
    TOOL = "tool"  # a forced tool call (Anthropic)


class AiError(Exception):
    """A call did not give a usable answer. `kind` decides what the gateway does next
    (ADR-0027 §4): quota and unavailable may be retried or fall back to the next provider;
    refused, blocked and budget stop; invalid gets one repair."""

    KINDS = frozenset({"quota", "unavailable", "refused", "blocked", "budget", "invalid"})

    def __init__(self, kind: str, detail: str = "", retry_after: float | None = None) -> None:
        if kind not in self.KINDS:
            raise ValueError(kind)
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.detail = detail
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class ModelEntry:
    provider: str  # kind of provider: ollama, groq, openrouter, openai, anthropic…
    model: str
    protocol: Protocol
    structured_output: StructuredOutput
    context: int  # tokens
    price_in: Decimal  # per million input tokens, in the currency of the budgets
    price_out: Decimal
    status: Status
    paid: bool
    local: bool  # runs on a machine of the user (Ollama): no data leaves it

    @classmethod
    def of(cls, data: Mapping[str, Any]) -> "ModelEntry":
        return cls(
            provider=str(data["provider"]),
            model=str(data["model"]),
            protocol=Protocol(data["protocol"]),
            structured_output=StructuredOutput(data["structured_output"]),
            context=int(data["context"]),
            price_in=Decimal(str(data["price_in"])),
            price_out=Decimal(str(data["price_out"])),
            status=Status(data["status"]),
            paid=bool(data["paid"]),
            local=bool(data.get("local", False)),
        )


@dataclass(frozen=True, slots=True)
class Catalogue:
    entries: tuple[ModelEntry, ...]
    currency: str = "EUR"

    @classmethod
    def of(cls, data: Mapping[str, Any]) -> "Catalogue":
        entries = tuple(ModelEntry.of(entry) for entry in data["models"])
        keys = [(e.provider, e.model) for e in entries]
        if len(set(keys)) != len(keys):
            raise ValueError("a model appears twice in the catalogue")
        for entry in entries:
            if entry.paid and entry.status is not Status.BLOCKED:
                # ADR-0027 §2: a paid provider is allowed by the administrator, never by data.
                raise ValueError(f"paid model {entry.provider}/{entry.model} must be blocked")
        return cls(entries, str(data.get("currency", "EUR")))

    def find(self, provider: str, model: str) -> ModelEntry | None:
        return next((e for e in self.entries if (e.provider, e.model) == (provider, model)), None)

    def providers(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(e.provider for e in self.entries))


@dataclass(frozen=True, slots=True)
class Message:
    role: str  # system, user or assistant
    content: str


@dataclass(frozen=True, slots=True)
class Answer:
    text: str  # the JSON of the structured output
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True, slots=True)
class Completion:
    """One call to a provider: what an adapter needs, nothing more."""

    endpoint: str  # base URL of the provider's API
    api_key: str | None
    model: ModelEntry
    messages: tuple[Message, ...]
    schema: Mapping[str, Any]  # JSON Schema of the structured output
    schema_name: str
    max_output_tokens: int
    timeout_seconds: float


def estimate_cost(
    model: ModelEntry, messages: Sequence[Message], max_output_tokens: int
) -> Decimal:
    """The most a call may cost, reserved before it (ADR-0027 §3): input tokens estimated from
    characters with a 20 % margin, plus the maximum output."""
    characters = sum(len(m.content) for m in messages)
    tokens_in = Decimal(characters) / CHARACTERS_PER_TOKEN * INPUT_MARGIN
    return (tokens_in * model.price_in + Decimal(max_output_tokens) * model.price_out) / PER_MILLION


def real_cost(model: ModelEntry, answer: Answer) -> Decimal:
    return (
        Decimal(answer.tokens_in) * model.price_in + Decimal(answer.tokens_out) * model.price_out
    ) / PER_MILLION
