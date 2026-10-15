# SPDX-License-Identifier: AGPL-3.0-or-later
"""S4: budget with reservation in PostgreSQL (docs/spikes/S4.md §3.4).

One row per budget scope. reserve() adds the estimated maximum cost to "reserved" in one
conditional UPDATE (row lock), refused when spent + reserved + estimate would exceed the
limit minus a guard band kept for overruns (a provider charging more than estimated).
settle() replaces the reservation by the real cost. Every write appends to budget_log the
value of spent + reserved right after it, for the check of criterion C2.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import psycopg

GUARD_BAND = 0.10  # share of the limit kept back for overruns


class BudgetExceeded(Exception):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS budget (scope text PRIMARY KEY, budget_limit numeric NOT NULL,
    spent numeric NOT NULL DEFAULT 0, reserved numeric NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS budget_log (id bigserial PRIMARY KEY, scope text NOT NULL,
    at timestamptz NOT NULL DEFAULT clock_timestamp(), action text NOT NULL, amount numeric NOT NULL,
    committed numeric NOT NULL);
"""


@dataclass
class Reservation:
    amount: float


class Budget:
    def __init__(self, scope: str, url: str | None = None) -> None:
        self.scope, self.url = scope, url or os.environ["S4_DATABASE_URL"]

    def create(self, limit: float) -> None:
        with psycopg.connect(self.url, autocommit=True) as connection:
            connection.execute(SCHEMA)  # type: ignore[arg-type]
            connection.execute("DELETE FROM budget_log WHERE scope = %s", (self.scope,))
            connection.execute(
                "INSERT INTO budget (scope, budget_limit) VALUES (%s, %s) ON CONFLICT (scope) DO UPDATE SET budget_limit = EXCLUDED.budget_limit, spent = 0, reserved = 0",
                (self.scope, limit),
            )

    def reserve(self, amount: float) -> Reservation:
        with psycopg.connect(self.url) as connection:
            row = connection.execute(
                "UPDATE budget SET reserved = reserved + %(a)s WHERE scope = %(s)s"
                " AND spent + reserved + %(a)s <= budget_limit * (1 - %(g)s) RETURNING spent + reserved",
                {"a": amount, "s": self.scope, "g": GUARD_BAND},
            ).fetchone()
            if row is None:
                connection.rollback()
                raise BudgetExceeded(self.scope)
            connection.execute("INSERT INTO budget_log (scope, action, amount, committed) VALUES (%s, 'reserve', %s, %s)", (self.scope, amount, row[0]))
        return Reservation(amount)

    def settle(self, reservation: Reservation, cost: float) -> None:
        with psycopg.connect(self.url) as connection:
            row = connection.execute(
                "UPDATE budget SET reserved = reserved - %(r)s, spent = spent + %(c)s WHERE scope = %(s)s RETURNING spent + reserved",
                {"r": reservation.amount, "c": cost, "s": self.scope},
            ).fetchone()
            assert row is not None
            connection.execute("INSERT INTO budget_log (scope, action, amount, committed) VALUES (%s, 'settle', %s, %s)", (self.scope, cost, row[0]))

    def state(self) -> dict[str, float]:
        with psycopg.connect(self.url) as connection:
            limit, spent, reserved = connection.execute("SELECT budget_limit, spent, reserved FROM budget WHERE scope = %s", (self.scope,)).fetchone()  # type: ignore[misc]
            peak = connection.execute("SELECT max(committed) FROM budget_log WHERE scope = %s", (self.scope,)).fetchone()[0]  # type: ignore[index]
        return {"limit": float(limit), "spent": float(spent), "reserved": float(reserved), "peak_committed": float(peak or 0)}


def new_scope() -> str:
    return f"s4-{uuid.uuid4().hex[:8]}"
