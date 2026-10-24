# SPDX-License-Identifier: AGPL-3.0-or-later
"""The model of the Assistant de veille, on the AI gateway (F05): the profile of the author,
in the worker, the only process that opens the keys of providers (DR6)."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from otlet.ai.application.gateway import Gateway, Request
from otlet.ai.domain.model import Message
from otlet.assistant.application.dossiers import Asked

USAGE = "veille"
SCHEMA_NAME = "veille"
TIMEOUT_SECONDS = 300.0


class GatewayModel:
    def __init__(self, gateway: Gateway) -> None:
        self._gateway = gateway

    def ask(
        self,
        user_id: UUID,
        system: str,
        user: str,
        schema: dict[str, Any],
        validate: Callable[[str], list[str]],
        max_output_tokens: int,
    ) -> Asked:
        outcome = self._gateway.generate(
            user_id,
            Request(
                usage=USAGE,
                messages=(Message("system", system), Message("user", user)),
                schema=schema,
                schema_name=SCHEMA_NAME,
                max_output_tokens=max_output_tokens,
                timeout_seconds=TIMEOUT_SECONDS,
            ),
            validate,
        )
        return Asked(
            text=outcome.text,
            error=outcome.error,
            model=None if outcome.model is None else outcome.model.model,
            attempts=tuple(
                {
                    "provider": a.provider_kind,
                    "model": a.model,
                    "result": a.result,
                    "seconds": a.seconds,
                    "tokens_in": a.tokens_in,
                    "tokens_out": a.tokens_out,
                }
                for a in outcome.attempts
            ),
        )
