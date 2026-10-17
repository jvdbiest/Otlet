# SPDX-License-Identifier: AGPL-3.0-or-later
"""The monthly budget of a user (ADR-0027 §3): the user sets the limit, the gateway reserves
before each call and settles after it."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from otlet.ai.application.ports import BudgetStore
from otlet.ai.domain.budget import BudgetState, Reservation, check_limit, month_of
from otlet.ai.domain.model import AiError


class Budget:
    def __init__(
        self, store: BudgetStore, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._store = store
        self._clock = clock

    def state(self, user_id: UUID) -> BudgetState:
        return self._store.state(user_id, month_of(self._clock()))

    def set_limit(self, user_id: UUID, limit: Decimal) -> BudgetState:
        self._store.set_limit(user_id, month_of(self._clock()), check_limit(limit))
        return self.state(user_id)

    def reserve(self, user_id: UUID, amount: Decimal) -> Reservation:
        """Raises AiError("budget") when the call could go beyond the month's budget."""
        reservation = self._store.reserve(user_id, month_of(self._clock()), amount)
        if reservation is None:
            raise AiError("budget", f"{amount} would go beyond the budget of the month")
        return reservation

    def settle(self, reservation: Reservation, cost: Decimal) -> None:
        self._store.settle(reservation, cost)
