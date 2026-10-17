# SPDX-License-Identifier: AGPL-3.0-or-later
"""`generate` (F05, ADR-0027 §4): the order of the profile, retries, fallbacks, the repair, the
budget and the journal, with in-memory providers."""

import json
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from otlet.ai.adapters.catalogue_file import PackagedCatalogue
from otlet.ai.application.budget import Budget
from otlet.ai.application.gateway import Attempt, Gateway, Request
from otlet.ai.application.ports import Adapter
from otlet.ai.domain.budget import BudgetState, Reservation
from otlet.ai.domain.model import AiError, Answer, Completion, Message, ModelEntry
from otlet.ai.domain.settings import InstancePolicy, Profile, ProfileEntry, Provider

USER = uuid.uuid4()
CATALOGUE = PackagedCatalogue().load()
NOW = datetime(2026, 10, 17, tzinfo=UTC)


class Settings:
    def __init__(
        self, providers: list[Provider], entries: list[ProfileEntry], policy: InstancePolicy
    ) -> None:
        self.providers, self.entries, self._policy = providers, entries, policy

    def list_providers(self, user_id: UUID) -> list[Provider]:
        return self.providers

    def profile(self, user_id: UUID) -> Profile:
        return Profile(tuple(self.entries))

    def policy(self) -> InstancePolicy:
        return self._policy


class Budgets:
    def __init__(self, limit: Decimal) -> None:
        self.limit, self.spent, self.reserved = limit, Decimal(0), Decimal(0)

    def limit_of(self) -> Decimal:
        return self.limit

    def state(self, user_id: UUID, month: date) -> BudgetState:
        return BudgetState(month, self.limit, self.spent, self.reserved)

    def reserve(self, user_id: UUID, month: date, amount: Decimal) -> Reservation | None:
        if self.spent + self.reserved + amount > self.limit * Decimal("0.9"):
            return None
        self.reserved += amount
        return Reservation(user_id, month, amount)

    def settle(self, reservation: Reservation, cost: Decimal) -> None:
        self.reserved -= reservation.amount
        self.spent += cost


class Scripted:
    """A provider whose answers are given in advance: a JSON text, or an AiError."""

    def __init__(self, script: list[str | AiError]) -> None:
        self.script = deque(script)
        self.calls: list[Completion] = []

    def complete(self, call: Completion) -> Answer:
        self.calls.append(call)
        step = self.script.popleft() if self.script else '{"title": "T"}'
        if isinstance(step, AiError):
            raise step
        return Answer(step, 100, 50)


class Journal:
    def __init__(self) -> None:
        self.attempts: list[Attempt] = []

    def record(self, user_id: UUID, attempt: Attempt) -> None:
        self.attempts.append(attempt)


def provider(kind: str, name: str) -> Provider:
    return Provider(uuid.uuid4(), USER, name, kind, f"https://{kind}.example", "1234", NOW)


def valid(text: str) -> list[str]:
    try:
        return [] if "title" in json.loads(text) else ["title: missing"]
    except json.JSONDecodeError:
        return ["not JSON"]


REQUEST = Request("check", (Message("user", "Hello"),), {"type": "object"}, "answer", 100)


def world(
    scripts: dict[str, Scripted],
    *,
    paid_allowed: bool = True,
    limit: Decimal = Decimal(10),
) -> tuple[Gateway, Journal, Budgets, list[float]]:
    local, groq = provider("ollama", "local"), provider("groq", "groq")
    entries = [
        ProfileEntry(local.id, "qwen2.5:1.5b-instruct"),
        ProfileEntry(groq.id, "llama-3.3-70b-versatile"),
    ]
    policy = InstancePolicy(allowed_paid=frozenset({"groq"}) if paid_allowed else frozenset())
    journal, budgets = Journal(), Budgets(limit)
    slept: list[float] = []

    def by_kind(_policy: InstancePolicy) -> Callable[[ModelEntry], Adapter]:
        return lambda model: scripts[model.provider]

    gateway = Gateway(
        Settings([local, groq], entries, policy),
        CATALOGUE,
        type("Keys", (), {"open": lambda self, user_id, provider_id: "key"})(),
        Budget(budgets, clock=lambda: NOW),  # type: ignore[arg-type]
        by_kind,
        journal,
        sleep=slept.append,
    )
    return gateway, journal, budgets, slept


def test_the_first_model_answers() -> None:
    local = Scripted(['{"title": "Bonjour"}'])
    gateway, journal, _, _ = world({"ollama": local, "groq": Scripted([])})
    outcome = gateway.generate(USER, REQUEST, valid)
    assert (outcome.text, outcome.error, outcome.model.provider if outcome.model else None) == (
        '{"title": "Bonjour"}',
        None,
        "ollama",
    )
    assert [a.result for a in journal.attempts] == ["ok"]
    assert local.calls[0].api_key == "key"


def test_an_invalid_output_gets_one_repair_on_the_same_model() -> None:
    local = Scripted(["{not json", '{"title": "Réparé"}'])
    gateway, _, _, _ = world({"ollama": local, "groq": Scripted([])})
    outcome = gateway.generate(USER, REQUEST, valid)
    assert (outcome.text, outcome.repaired) == ('{"title": "Réparé"}', True)
    assert local.calls[1].messages[-1].content.startswith("The JSON is invalid: not JSON")
    twice = Scripted(["{not json", "{still not"])
    gateway, _, _, _ = world({"ollama": twice, "groq": Scripted([])})
    assert gateway.generate(USER, REQUEST, valid).error == "invalid"


def test_an_answer_cut_by_the_room_left_is_not_repaired() -> None:
    class Cut(Scripted):
        def complete(self, call: Completion) -> Answer:
            self.calls.append(call)
            return Answer('{"title": "cut in the mid', 3000, 1096, truncated=True)

    local = Cut([])
    gateway, journal, _, _ = world({"ollama": local, "groq": Scripted([])})
    outcome = gateway.generate(USER, REQUEST, valid)
    assert (outcome.error, outcome.text, len(local.calls)) == ("out_of_room", None, 1)


def test_a_short_quota_wait_is_retried_then_the_next_model_takes_over() -> None:
    local = Scripted([AiError("quota", retry_after=1.0), '{"title": "T"}'])
    gateway, _, _, slept = world({"ollama": local, "groq": Scripted([])})
    assert gateway.generate(USER, REQUEST, valid).text == '{"title": "T"}'
    assert slept == [1.0]
    long_wait = Scripted([AiError("quota", retry_after=30.0)])
    groq = Scripted(['{"title": "Groq"}'])
    gateway, journal, _, slept = world({"ollama": long_wait, "groq": groq})
    outcome = gateway.generate(USER, REQUEST, valid)
    assert (outcome.text, slept) == ('{"title": "Groq"}', [])
    assert [a.result for a in journal.attempts] == ["quota", "ok"]


def test_an_unavailable_model_gets_one_more_try_then_falls_back() -> None:
    local = Scripted([AiError("unavailable"), AiError("unavailable")])
    gateway, journal, _, _ = world({"ollama": local, "groq": Scripted([])})
    outcome = gateway.generate(USER, REQUEST, valid)
    assert outcome.model is not None and outcome.model.provider == "groq"
    assert [a.result for a in journal.attempts] == ["unavailable", "unavailable", "ok"]


def test_a_refused_request_stops_at_once() -> None:
    local = Scripted([AiError("refused", "HTTP 400")])
    groq = Scripted([])
    gateway, _, _, _ = world({"ollama": local, "groq": groq})
    assert gateway.generate(USER, REQUEST, valid).error == "refused"
    assert groq.calls == [] and len(local.calls) == 1


def test_a_blocked_model_is_skipped_before_any_call() -> None:
    local = Scripted([AiError("unavailable"), AiError("unavailable")])
    groq = Scripted([])
    gateway, journal, _, _ = world({"ollama": local, "groq": groq}, paid_allowed=False)
    outcome = gateway.generate(USER, REQUEST, valid)
    assert outcome.error == "blocked" and groq.calls == []
    assert [a.result for a in journal.attempts] == ["unavailable", "unavailable", "blocked"]


def test_the_budget_is_reserved_before_and_settled_after_each_call() -> None:
    groq_only = Scripted([])
    gateway, _, budgets, _ = world({"ollama": Scripted([AiError("refused")]), "groq": groq_only})
    gateway.generate(USER, REQUEST, valid)  # the local model costs nothing, even refused
    assert (budgets.spent, budgets.reserved) == (Decimal(0), Decimal(0))
    local = Scripted([AiError("unavailable"), AiError("unavailable")])
    gateway, journal, budgets, _ = world({"ollama": local, "groq": Scripted([])}, limit=Decimal(0))
    outcome = gateway.generate(USER, REQUEST, valid)  # Groq is paid, and there is no budget
    assert outcome.error == "budget" and budgets.reserved == 0
    assert journal.attempts[-1].result == "budget"
    paid = Scripted(['{"title": "T"}'])
    gateway, journal, budgets, _ = world(
        {"ollama": local.__class__([AiError("unavailable")] * 2), "groq": paid}
    )
    gateway.generate(USER, REQUEST, valid)
    expected = (Decimal(100) * Decimal("0.55") + Decimal(50) * Decimal("0.75")) / 1_000_000
    assert (budgets.spent, budgets.reserved, journal.attempts[-1].cost) == (
        expected,
        Decimal(0),
        expected,
    )


def test_without_a_profile_nothing_is_called() -> None:
    gateway, journal, _, _ = world({"ollama": Scripted([]), "groq": Scripted([])})
    gateway._settings.entries = []  # type: ignore[attr-defined]
    assert gateway.generate(USER, REQUEST, valid).error == "no_profile"
    assert journal.attempts == []


def test_an_error_kind_is_known() -> None:
    with pytest.raises(ValueError):
        AiError("nonsense")
