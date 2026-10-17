# SPDX-License-Identifier: AGPL-3.0-or-later
"""The catalogue of models and the cost of a call (F05, ADR-0027 §2, §3)."""

from decimal import Decimal

import pytest

from otlet.ai.adapters.catalogue_file import PackagedCatalogue
from otlet.ai.domain.model import (
    AiError,
    Answer,
    Catalogue,
    Message,
    Status,
    estimate_cost,
    real_cost,
)


def entry(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "provider": "groq",
        "protocol": "openai",
        "model": "m",
        "structured_output": "json_schema",
        "context": 1000,
        "price_in": 1,
        "price_out": 2,
        "status": "blocked",
        "paid": True,
    }
    data.update(changes)
    return data


def test_the_packaged_catalogue_is_valid_and_keeps_paid_providers_blocked() -> None:
    catalogue = PackagedCatalogue().load()
    local = catalogue.find("ollama", "qwen2.5:1.5b-instruct")
    assert local is not None and local.status is Status.TESTED and local.local
    assert all(e.status is Status.BLOCKED for e in catalogue.entries if e.paid)
    assert "anthropic" in catalogue.providers()


def test_a_paid_model_cannot_be_allowed_by_data() -> None:
    with pytest.raises(ValueError, match="must be blocked"):
        Catalogue.of({"models": [entry(status="untested")]})
    with pytest.raises(ValueError, match="twice"):
        Catalogue.of({"models": [entry(), entry()]})


def test_the_reservation_covers_the_call() -> None:
    model = Catalogue.of({"models": [entry(price_in=3, price_out=12)]}).entries[0]
    messages = [Message("system", "x" * 700), Message("user", "y" * 700)]
    # 1 400 characters / 3.5 × 1.2 = 480 input tokens, plus 1 000 output tokens at most.
    assert estimate_cost(model, messages, 1000) == Decimal(480 * 3 + 1000 * 12) / 1_000_000
    assert real_cost(model, Answer("{}", 400, 500)) == Decimal(400 * 3 + 500 * 12) / 1_000_000
    assert real_cost(model, Answer("{}", 400, 500)) < estimate_cost(model, messages, 1000)


def test_errors_have_known_kinds() -> None:
    assert AiError("quota", retry_after=1.5).retry_after == 1.5
    with pytest.raises(ValueError):
        AiError("oops")
