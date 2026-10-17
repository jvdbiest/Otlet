# SPDX-License-Identifier: AGPL-3.0-or-later
"""The monthly budget with reservation (F05, ADR-0027 §3; S4, criterion C2): never overrun,
even by concurrent calls; the real cost replaces the reservation; a new month starts afresh."""

import threading
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.ai.adapters.budget_postgres import PostgresBudget
from otlet.ai.application.budget import Budget
from otlet.ai.domain.model import AiError
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db

pytestmark = requires_database

OCTOBER = datetime(2026, 10, 17, 12, tzinfo=UTC)
NOVEMBER = datetime(2026, 11, 2, 9, tzinfo=UTC)


def user(engine: sa.Engine, login: str) -> uuid.UUID:
    created: uuid.UUID = Authentication(PostgresIdentityStore(engine), Argon2Hasher()).create_user(
        login, login, "une phrase de passe assez longue"
    )
    return created


def test_free_models_run_without_budget_and_paid_ones_need_one(migrated: TestDatabase) -> None:
    engine = db.create_engine(migrated.app_url)
    alice = user(engine, "alice@example.org")
    budget = Budget(PostgresBudget(engine), clock=lambda: OCTOBER)
    budget.settle(budget.reserve(alice, Decimal(0)), Decimal(0))  # a local model costs nothing
    with pytest.raises(AiError) as caught:
        budget.reserve(alice, Decimal("0.001"))
    assert caught.value.kind == "budget"


def test_reservations_hold_the_guard_band_and_settle_to_the_real_cost(
    migrated: TestDatabase,
) -> None:
    engine = db.create_engine(migrated.app_url)
    alice, bob = user(engine, "alice@example.org"), user(engine, "bob@example.org")
    clock = [OCTOBER]
    budget = Budget(PostgresBudget(engine), clock=lambda: clock[0])
    state = budget.set_limit(alice, Decimal(10))
    assert (state.limit, state.usable) == (Decimal(10), Decimal(9))  # 10 % kept back
    first = budget.reserve(alice, Decimal(6))
    with pytest.raises(AiError):
        budget.reserve(alice, Decimal(4))  # 6 + 4 > 9
    budget.settle(first, Decimal("1.5"))  # cost less than reserved
    state = budget.state(alice)
    assert (state.spent, state.reserved, state.usable) == (
        Decimal("1.5"),
        Decimal(0),
        Decimal("7.5"),
    )
    budget.reserve(alice, Decimal(4))
    assert budget.state(bob).limit == 0  # Bob's budget is his own
    # A new month starts afresh, with the same limit.
    clock[0] = NOVEMBER
    november = budget.state(alice)
    assert (november.spent, november.reserved, november.limit) == (
        Decimal(0),
        Decimal(0),
        Decimal(10),
    )


def test_concurrent_reservations_never_overrun(migrated: TestDatabase) -> None:
    engine = db.create_engine(migrated.app_url, pool_size=10)
    alice = user(engine, "alice@example.org")
    budget = Budget(PostgresBudget(engine), clock=lambda: OCTOBER)
    budget.set_limit(alice, Decimal(10))  # 9 usable: 9 reservations of 1 at most
    granted: list[bool] = []
    lock = threading.Lock()

    def call() -> None:
        try:
            budget.reserve(alice, Decimal(1))
            outcome = True
        except AiError:
            outcome = False
        with lock:
            granted.append(outcome)

    threads = [threading.Thread(target=call) for _ in range(30)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert granted.count(True) == 9
    assert budget.state(alice).reserved == Decimal(9)
