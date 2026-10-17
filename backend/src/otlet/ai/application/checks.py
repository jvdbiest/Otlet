# SPDX-License-Identifier: AGPL-3.0-or-later
"""« Tester » : one small structured answer through the user's profile, run by the worker,
read by the interface (F05, acceptance: « un appel structuré réussit avec Ollama »)."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from otlet.ai.application.gateway import Gateway, Outcome, Request
from otlet.ai.domain.model import Message

CHECK_PROFILE = "ai.check_profile"

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
    },
    "required": ["title", "keywords"],
}
REQUEST = Request(
    usage="check",
    messages=(
        Message("system", "Tu réponds uniquement par un objet JSON conforme au schéma demandé."),
        Message(
            "user",
            "Donne un titre et exactement trois mots-clés pour un article sur la veille "
            "informationnelle avec des logiciels libres.",
        ),
    ),
    schema=SCHEMA,
    schema_name="check",
    max_output_tokens=200,
)


def validate(text: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        return [f"not JSON: {error.msg}"]
    errors = []
    if not isinstance(data, dict) or not isinstance(data.get("title"), str) or not data["title"]:
        errors.append("title: a non-empty string is required")
    keywords = data.get("keywords") if isinstance(data, dict) else None
    if (
        not isinstance(keywords, list)
        or len(keywords) != 3
        or not all(isinstance(k, str) for k in keywords)
    ):
        errors.append("keywords: exactly three strings are required")
    return errors


@dataclass(frozen=True, slots=True)
class Check:
    id: UUID
    created_at: datetime
    finished_at: datetime | None
    result: dict[str, Any] | None


class CheckStore(Protocol):
    def create(self, user_id: UUID, check_id: UUID) -> Check:
        """Creates the check and enqueues its job in the same transaction."""
        ...

    def get(self, user_id: UUID, check_id: UUID) -> Check | None: ...

    def finish(self, user_id: UUID, check_id: UUID, result: dict[str, Any]) -> None: ...


def summary(outcome: Outcome) -> dict[str, Any]:
    """What the interface shows of a check: never the key, never the prompt."""
    return {
        "ok": outcome.error is None and outcome.text is not None,
        "error": outcome.error,
        "provider": None if outcome.model is None else outcome.model.provider,
        "model": None if outcome.model is None else outcome.model.model,
        "answer": None if outcome.text is None else json.loads(outcome.text),
        "repaired": outcome.repaired,
        "attempts": [
            {
                "provider": a.provider_kind,
                "model": a.model,
                "result": a.result,
                "detail": a.detail,
                "seconds": a.seconds,
                "tokens_in": a.tokens_in,
                "tokens_out": a.tokens_out,
                "cost": str(a.cost),
            }
            for a in outcome.attempts
        ],
    }


def run_check(gateway: Gateway, store: CheckStore, user_id: UUID, check_id: UUID) -> None:
    """Each model of the profile in turn, alone: a test says which models answer, where a
    generation stops at the first that does. The first model gives the summary on top."""
    entries = gateway.profile(user_id)
    if not entries:
        store.finish(user_id, check_id, summary(gateway.generate(user_id, REQUEST, validate)))
        return
    models = [summary(gateway.generate(user_id, REQUEST, validate, [entry])) for entry in entries]
    store.finish(
        user_id, check_id, {**models[0], "ok": all(m["ok"] for m in models), "models": models}
    )
