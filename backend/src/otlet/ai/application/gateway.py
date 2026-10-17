# SPDX-License-Identifier: AGPL-3.0-or-later
"""The gateway: `generate`, the one way the rest of Otlet asks an AI for something (F05,
ADR-0027). It runs in the worker, the only process that can open the keys of providers (DR6).

For a request, the gateway tries the models of the user's profile, in order:

- a model blocked by the instance is skipped before any call;
- before each call, the most it may cost is reserved on the user's budget; a refused
  reservation stops everything (« budget »); the real cost replaces it afterwards;
- 429 with a Retry-After of 2 s at most: wait, then up to two more tries on the same model;
  then the next model;
- 5xx or timeout: one more try, then the next model;
- 400 (refused): stop at once, no retry, no fallback;
- 404 (no such model or address on that engine): the next model;
- an output that fails validation: one repair, on the same model, with the errors.

Every attempt is written to the call journal of the user.
"""

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from otlet.ai.application.budget import Budget
from otlet.ai.application.ports import Adapter
from otlet.ai.domain.model import (
    AiError,
    Answer,
    Catalogue,
    Completion,
    Message,
    ModelEntry,
    Status,
    estimate_cost,
    real_cost,
)
from otlet.ai.domain.settings import InstancePolicy, Profile, Provider, api_endpoint

RETRY_AFTER_MAX = 2.0
QUOTA_RETRIES = 2
UNAVAILABLE_RETRIES = 1

# Checks a raw output; answers the list of errors, empty when the output is usable.
Validate = Callable[[str], list[str]]


class KeyOpener(Protocol):
    def open(self, user_id: UUID, provider_id: UUID) -> str | None:
        """The plaintext key of a provider of the user, or None when it has none."""
        ...


class ProfileSource(Protocol):
    """What the gateway reads of the AI settings."""

    def list_providers(self, user_id: UUID) -> list[Provider]: ...

    def profile(self, user_id: UUID) -> Profile: ...

    def policy(self) -> InstancePolicy: ...


class CallJournal(Protocol):
    def record(self, user_id: UUID, attempt: "Attempt") -> None: ...


AdapterFactory = Callable[[InstancePolicy], Callable[[ModelEntry], Adapter]]


@dataclass(frozen=True, slots=True)
class Request:
    usage: str  # what the call is for: « redaction », « check »…
    messages: tuple[Message, ...]
    schema: Mapping[str, Any]
    schema_name: str
    max_output_tokens: int = 1200
    timeout_seconds: float = 120.0


@dataclass(frozen=True, slots=True)
class Attempt:
    usage: str
    provider_id: UUID | None
    provider_kind: str
    model: str
    result: str  # ok, or the kind of the error
    detail: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost: Decimal = Decimal(0)
    seconds: float = 0.0
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Outcome:
    text: str | None = None
    error: str | None = None  # no_profile, budget, refused, invalid, quota, unavailable
    model: ModelEntry | None = None
    provider_id: UUID | None = None
    repaired: bool = False
    attempts: list[Attempt] = field(default_factory=list)


class Gateway:
    def __init__(
        self,
        settings: ProfileSource,
        catalogue: Catalogue,
        keys: KeyOpener,
        budget: Budget,
        adapters: AdapterFactory,
        journal: CallJournal,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._catalogue = catalogue
        self._keys = keys
        self._budget = budget
        self._adapters = adapters
        self._journal = journal
        self._sleep = sleep

    def generate(self, user_id: UUID, request: Request, validate: Validate) -> Outcome:
        outcome = Outcome()
        policy = self._settings.policy()
        adapter_for = self._adapters(policy)
        providers = {p.id: p for p in self._settings.list_providers(user_id)}
        entries = self._settings.profile(user_id).entries
        if not entries:
            outcome.error = "no_profile"
            return outcome
        for entry in entries:
            provider = providers.get(entry.provider_id)
            model = None if provider is None else self._catalogue.model(provider.kind, entry.model)
            if provider is None or model is None or policy.status(model) is Status.BLOCKED:
                self._note(
                    user_id,
                    outcome,
                    Attempt(
                        request.usage,
                        entry.provider_id,
                        "" if provider is None else provider.kind,
                        entry.model,
                        "blocked",
                    ),
                )
                outcome.error = "blocked"
                continue
            try:
                return self._on_model(
                    user_id, request, validate, provider, model, adapter_for(model), outcome
                )
            except AiError as error:
                outcome.error = error.kind
                if error.kind in ("budget", "refused"):
                    return outcome
                # quota or unavailable: the next model of the profile
        return outcome

    def _on_model(
        self,
        user_id: UUID,
        request: Request,
        validate: Validate,
        provider: Provider,
        model: ModelEntry,
        adapter: Adapter,
        outcome: Outcome,
    ) -> Outcome:
        key = self._keys.open(user_id, provider.id)
        messages = request.messages
        answer = self._with_retries(
            user_id, request, provider, model, adapter, key, messages, outcome
        )
        errors = validate(answer.text)
        if errors:  # one repair, on the same model
            outcome.repaired = True
            messages = (
                *messages,
                Message("assistant", answer.text),
                Message(
                    "user",
                    "The JSON is invalid: "
                    + "; ".join(errors)[:1000]
                    + ". Answer again with the corrected JSON only.",
                ),
            )
            answer = self._with_retries(
                user_id, request, provider, model, adapter, key, messages, outcome
            )
            errors = validate(answer.text)
        outcome.model, outcome.provider_id = model, provider.id
        if errors:
            outcome.error = "invalid"
            outcome.text = None
        else:
            outcome.error = None  # an earlier model's failure is superseded by this answer
            outcome.text = answer.text
        return outcome

    def _with_retries(
        self,
        user_id: UUID,
        request: Request,
        provider: Provider,
        model: ModelEntry,
        adapter: Adapter,
        key: str | None,
        messages: Sequence[Message],
        outcome: Outcome,
    ) -> Answer:
        quota_retries = unavailable_retries = 0
        while True:
            try:
                return self._once(
                    user_id, request, provider, model, adapter, key, messages, outcome
                )
            except AiError as error:
                if (
                    error.kind == "quota"
                    and quota_retries < QUOTA_RETRIES
                    and (error.retry_after or 0) <= RETRY_AFTER_MAX
                ):
                    quota_retries += 1
                    self._sleep(error.retry_after or 1.0)
                    continue
                if error.kind == "unavailable" and unavailable_retries < UNAVAILABLE_RETRIES:
                    unavailable_retries += 1
                    continue
                raise

    def _once(
        self,
        user_id: UUID,
        request: Request,
        provider: Provider,
        model: ModelEntry,
        adapter: Adapter,
        key: str | None,
        messages: Sequence[Message],
        outcome: Outcome,
    ) -> Answer:
        def attempt(result: str, **values: Any) -> Attempt:
            return Attempt(request.usage, provider.id, provider.kind, model.model, result, **values)

        try:
            reservation = self._budget.reserve(
                user_id, estimate_cost(model, messages, request.max_output_tokens)
            )
        except AiError as error:
            self._note(user_id, outcome, attempt("budget", detail=error.detail[:200]))
            raise
        started = time.perf_counter()
        try:
            answer = adapter.complete(
                Completion(
                    endpoint=api_endpoint(provider.endpoint, self._local(provider)),
                    api_key=key,
                    model=model,
                    messages=tuple(messages),
                    schema=request.schema,
                    schema_name=request.schema_name,
                    max_output_tokens=request.max_output_tokens,
                    timeout_seconds=request.timeout_seconds,
                )
            )
        except AiError as error:
            self._budget.settle(reservation, Decimal(0))
            self._note(
                user_id,
                outcome,
                attempt(
                    error.kind,
                    detail=error.detail[:200],
                    seconds=round(time.perf_counter() - started, 2),
                ),
            )
            raise
        cost = real_cost(model, answer)
        self._budget.settle(reservation, cost)
        self._note(
            user_id,
            outcome,
            attempt(
                "ok",
                tokens_in=answer.tokens_in,
                tokens_out=answer.tokens_out,
                cost=cost,
                seconds=round(time.perf_counter() - started, 2),
            ),
        )
        return answer

    def _local(self, provider: Provider) -> bool:
        kind = self._catalogue.kind(provider.kind)
        return kind is not None and kind.custom_models

    def _note(self, user_id: UUID, outcome: Outcome, attempt: Attempt) -> None:
        outcome.attempts.append(attempt)
        self._journal.record(user_id, attempt)
