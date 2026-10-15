# SPDX-License-Identifier: AGPL-3.0-or-later
"""S4: minimal AI gateway on the official SDKs (TC-08), docs/spikes/S4.md §3.1.

Contract: generate(usage, brief, profile, budget) -> Outcome, with a validated draft or a
normalized error (quota, unavailable, invalid, budget, refused). No other code talks to a
provider SDK.

- Adapters: generic OpenAI-compatible (SDK openai, base URL), native Anthropic (SDK
  anthropic, structured output through a forced tool).
- Model table: models.json (capabilities, prices, status).
- Budget with reservation: budget.py, before every provider call.
- Retries and fallbacks: 429 with a short Retry-After, wait and retry up to twice, then the
  next provider of the profile; 5xx or timeout, retry once, then the next provider; 400,
  stop with "refused". One repair at most for an invalid output.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import anthropic
import openai

import draft
from budget import Budget, BudgetExceeded

HERE = Path(__file__).parent
MAX_OUTPUT_TOKENS = 1200
TIMEOUT_SECONDS = float(os.environ.get("S4_TIMEOUT", "30"))
RETRY_AFTER_MAX = 2.0


def table() -> list[dict[str, Any]]:
    return json.loads((HERE / "models.json").read_text(encoding="utf-8"))["models"]


def entry(provider: str) -> dict[str, Any]:
    return next(m for m in table() if m["provider"] == provider)


class GatewayError(Exception):
    def __init__(self, kind: str, detail: str = "", retry_after: float | None = None) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind, self.detail, self.retry_after = kind, detail, retry_after


@dataclass
class Answer:
    text: str
    tokens_in: int
    tokens_out: int


class Adapter(Protocol):
    def complete(self, model: str, messages: list[dict[str, str]], schema: dict[str, Any]) -> Answer: ...


@dataclass
class OpenAICompatible:
    base_url: str
    api_key: str = "none"

    def complete(self, model: str, messages: list[dict[str, str]], schema: dict[str, Any]) -> Answer:
        client = openai.OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=TIMEOUT_SECONDS)
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, max_tokens=MAX_OUTPUT_TOKENS, temperature=0.2,  # type: ignore[arg-type]
                response_format={"type": "json_schema", "json_schema": {"name": "article_draft", "schema": schema}},
            )
        except openai.RateLimitError as error:
            raise GatewayError("quota", str(error), retry_after(error.response.headers)) from error
        except openai.APITimeoutError as error:
            raise GatewayError("unavailable", "timeout") from error
        except openai.APIConnectionError as error:
            raise GatewayError("unavailable", "connection") from error
        except openai.APIStatusError as error:
            raise GatewayError("unavailable" if error.status_code >= 500 else "refused", f"HTTP {error.status_code}") from error
        usage = response.usage
        return Answer(response.choices[0].message.content or "", usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0)


@dataclass
class AnthropicNative:
    base_url: str
    api_key: str = "none"

    def complete(self, model: str, messages: list[dict[str, str]], schema: dict[str, Any]) -> Answer:
        client = anthropic.Anthropic(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=TIMEOUT_SECONDS)
        system = " ".join(m["content"] for m in messages if m["role"] == "system")
        try:
            response = client.messages.create(
                model=model, max_tokens=MAX_OUTPUT_TOKENS, system=system,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"],  # type: ignore[misc]
                tools=[{"name": "article_draft", "description": "Article draft", "input_schema": schema}],
                tool_choice={"type": "tool", "name": "article_draft"},
            )
        except anthropic.RateLimitError as error:
            raise GatewayError("quota", str(error), retry_after(error.response.headers)) from error
        except anthropic.APITimeoutError as error:
            raise GatewayError("unavailable", "timeout") from error
        except anthropic.APIConnectionError as error:
            raise GatewayError("unavailable", "connection") from error
        except anthropic.APIStatusError as error:
            raise GatewayError("unavailable" if error.status_code >= 500 else "refused", f"HTTP {error.status_code}") from error
        tool = next((b for b in response.content if b.type == "tool_use"), None)
        text = json.dumps(tool.input) if tool is not None else ""  # type: ignore[union-attr]
        return Answer(text, response.usage.input_tokens, response.usage.output_tokens)


def retry_after(headers: Any) -> float | None:
    try:
        return float(headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


def adapter_for(provider: str) -> Adapter:
    urls = json.loads(os.environ.get("S4_PROVIDERS", "{}"))  # {"ollama": "http://s4-ollama:11434/v1", ...}
    if entry(provider)["status"] == "blocked":
        raise GatewayError("refused", f"{provider} is blocked until Joël agrees (docs/spikes/S4.md §2)")
    if entry(provider)["protocol"] == "anthropic":
        return AnthropicNative(urls[provider])
    return OpenAICompatible(urls[provider])


def estimate_cost(provider: str, messages: list[dict[str, str]]) -> float:
    """Input estimated as characters / 3.5 with a 20 % margin, plus the maximum output."""
    model = entry(provider)
    tokens_in = sum(len(m["content"]) for m in messages) / 3.5 * 1.2
    return (tokens_in * model["price_in"] + MAX_OUTPUT_TOKENS * model["price_out"]) / 1_000_000


def real_cost(provider: str, answer: Answer) -> float:
    model = entry(provider)
    return (answer.tokens_in * model["price_in"] + answer.tokens_out * model["price_out"]) / 1_000_000


@dataclass
class Outcome:
    draft: draft.ArticleDraft | None = None
    error: str | None = None
    provider: str | None = None
    repaired: bool = False
    calls: list[dict[str, Any]] = field(default_factory=list)


def call_once(provider: str, messages: list[dict[str, str]], budget: Budget | None, outcome: Outcome) -> Answer:
    """One provider call, with its reservation; the reservation is always settled."""
    reservation = budget.reserve(estimate_cost(provider, messages)) if budget else None
    started = time.perf_counter()
    try:
        answer = adapter_for(provider).complete(entry(provider)["model"], messages, draft.SCHEMA)
    except GatewayError as error:
        if budget and reservation:
            budget.settle(reservation, 0.0)
        outcome.calls.append({"provider": provider, "error": error.kind, "detail": error.detail[:120], "seconds": round(time.perf_counter() - started, 2)})
        raise
    if budget and reservation:
        budget.settle(reservation, real_cost(provider, answer))
    outcome.calls.append({"provider": provider, "tokens_in": answer.tokens_in, "tokens_out": answer.tokens_out, "seconds": round(time.perf_counter() - started, 2)})
    return answer


def call_with_retries(provider: str, messages: list[dict[str, str]], budget: Budget | None, outcome: Outcome) -> Answer:
    quota_retries, other_retries = 0, 0
    while True:
        try:
            return call_once(provider, messages, budget, outcome)
        except GatewayError as error:
            if error.kind == "quota" and quota_retries < 2 and (error.retry_after or 0) <= RETRY_AFTER_MAX:
                quota_retries += 1
                time.sleep(error.retry_after or 1.0)
                continue
            if error.kind == "unavailable" and other_retries < 1:
                other_retries += 1
                continue
            raise


def generate(brief: draft.Brief, profile: list[str], budget: Budget | None = None) -> Outcome:
    """Usage "redaction": the profile is the user's ordered list of allowed providers."""
    outcome = Outcome()
    messages = draft.prompt(brief)
    for provider in profile:
        try:
            answer = call_with_retries(provider, messages, budget, outcome)
            result, errors = draft.validate(answer.text, brief)
            if result is None:  # one repair, on the same provider
                repair = [*messages, {"role": "assistant", "content": answer.text},
                          {"role": "user", "content": "The JSON is invalid: " + "; ".join(errors) + ". Answer again with the corrected JSON only."}]
                answer = call_with_retries(provider, repair, budget, outcome)
                result, errors = draft.validate(answer.text, brief)
                outcome.repaired = True
            outcome.provider = provider
            if result is None:
                outcome.error = "invalid: " + "; ".join(errors)[:300]
            else:
                outcome.draft = result
            return outcome
        except BudgetExceeded:
            outcome.error = "budget"
            return outcome
        except GatewayError as error:
            if error.kind == "refused":
                outcome.error = f"refused: {error.detail[:120]}"
                return outcome
            outcome.error = error.kind  # quota or unavailable: next provider
    return outcome
