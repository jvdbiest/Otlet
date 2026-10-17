# SPDX-License-Identifier: AGPL-3.0-or-later
"""The writer of drafts, on the AI gateway (F05): it runs in the worker, the only process that
opens the keys of providers (DR6)."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from otlet.ai.application.gateway import Gateway, ProfileSource, Request
from otlet.ai.domain.model import Catalogue, Message
from otlet.ai.domain.settings import LOCAL_DEFAULT_WINDOW, ProfileEntry, effective_window
from otlet.writing.application.drafts import TIMEOUT_SECONDS, Written
from otlet.writing.domain.brief import ModelChoice
from otlet.writing.domain.draft import SCHEMA_NAME

USAGE = "redaction"


class GatewayWriter:
    def __init__(self, gateway: Gateway, settings: ProfileSource, catalogue: Catalogue) -> None:
        self._gateway = gateway
        self._settings = settings
        self._catalogue = catalogue

    def room(self, user_id: UUID, model: ModelChoice | None) -> tuple[int, bool]:
        entries = self._entries(user_id, model)
        providers = {p.id: p for p in self._settings.list_providers(user_id)}
        first = next(iter(entries), None)
        provider = None if first is None else providers.get(first.provider_id)
        entry = (
            None
            if provider is None or first is None
            else self._catalogue.model(provider.kind, first.model)
        )
        if provider is None or entry is None:
            return LOCAL_DEFAULT_WINDOW, True  # unknown: the smallest room
        return effective_window(provider, entry.context, entry.local), entry.local

    def write(
        self,
        user_id: UUID,
        prompt: list[tuple[str, str]],
        schema: dict[str, Any],
        validate: Callable[[str], list[str]],
        model: ModelChoice | None,
        max_output_tokens: int,
    ) -> Written:
        outcome = self._gateway.generate(
            user_id,
            Request(
                usage=USAGE,
                messages=tuple(Message(role, content) for role, content in prompt),
                schema=schema,
                schema_name=SCHEMA_NAME,
                max_output_tokens=max_output_tokens,
                timeout_seconds=TIMEOUT_SECONDS,
            ),
            validate,
            None if model is None else [ProfileEntry(model.provider_id, model.model)],
        )
        return Written(
            text=outcome.text,
            error=outcome.error,
            provider_kind=None if outcome.model is None else outcome.model.provider,
            model=None if outcome.model is None else outcome.model.model,
            attempts=tuple(
                {
                    "provider": a.provider_kind,
                    "model": a.model,
                    "result": a.result,
                    "detail": a.detail,
                    "seconds": a.seconds,
                    "tokens_in": a.tokens_in,
                    "tokens_out": a.tokens_out,
                }
                for a in outcome.attempts
            ),
        )

    def _entries(self, user_id: UUID, model: ModelChoice | None) -> tuple[ProfileEntry, ...]:
        if model is not None:
            return (ProfileEntry(model.provider_id, model.model),)
        return tuple(self._settings.profile(user_id).entries)
