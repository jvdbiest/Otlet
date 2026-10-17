# SPDX-License-Identifier: AGPL-3.0-or-later
"""The monthly budget on PostgreSQL: the reservation is one conditional UPDATE of the month's
row, which locks it; concurrent reservations queue on that lock and each sees what the others
reserved (ADR-0027 §3, S4 criterion C2)."""

from datetime import date
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa

from otlet.ai.domain.budget import GUARD_BAND, BudgetState, Reservation
from otlet.platform.database import scoped_transaction

OWN = "user_id = :user"  # explicit, beside the policy (M-12)
# The month's row, created with the user's limit at the first reservation of the month.
MONTH_ROW = (
    "INSERT INTO ai_budget_months (user_id, month, budget_limit)"
    " VALUES (:user, :month, coalesce((SELECT monthly_limit FROM ai_budget_limits"
    "   WHERE user_id = :user), 0))"
    " ON CONFLICT (user_id, month) DO NOTHING"
)


class PostgresBudget:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def limit(self, user_id: UUID) -> Decimal:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            value = connection.execute(
                sa.text(f"SELECT monthly_limit FROM ai_budget_limits WHERE {OWN}"),
                {"user": user_id},
            ).scalar()
        return Decimal(0) if value is None else Decimal(value)

    def set_limit(self, user_id: UUID, month: date, limit: Decimal) -> None:
        """The new limit applies at once, to the current month too."""
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO ai_budget_limits (user_id, monthly_limit) VALUES (:user, :limit)"
                    " ON CONFLICT (user_id) DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit"
                ),
                {"user": user_id, "limit": limit},
            )
            connection.execute(sa.text(MONTH_ROW), {"user": user_id, "month": month})
            connection.execute(
                sa.text(
                    f"UPDATE ai_budget_months SET budget_limit = :limit WHERE {OWN}"
                    " AND month = :month"
                ),
                {"user": user_id, "month": month, "limit": limit},
            )

    def state(self, user_id: UUID, month: date) -> BudgetState:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            row = connection.execute(
                sa.text(
                    "SELECT budget_limit, spent, reserved FROM ai_budget_months"
                    f" WHERE {OWN} AND month = :month"
                ),
                {"user": user_id, "month": month},
            ).one_or_none()
        if row is None:
            return BudgetState(month, self.limit(user_id), Decimal(0), Decimal(0))
        return BudgetState(
            month, Decimal(row.budget_limit), Decimal(row.spent), Decimal(row.reserved)
        )

    def reserve(self, user_id: UUID, month: date, amount: Decimal) -> Reservation | None:
        """The reservation, or None when it would go beyond the limit minus the guard band."""
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            connection.execute(sa.text(MONTH_ROW), {"user": user_id, "month": month})
            done = connection.execute(
                sa.text(
                    "UPDATE ai_budget_months SET reserved = reserved + :amount"
                    f" WHERE {OWN} AND month = :month"
                    " AND spent + reserved + :amount <= budget_limit * (1 - :guard)"
                    " RETURNING 1"
                ),
                {"user": user_id, "month": month, "amount": amount, "guard": GUARD_BAND},
            ).one_or_none()
        return None if done is None else Reservation(user_id, month, amount)

    def settle(self, reservation: Reservation, cost: Decimal) -> None:
        """The real cost replaces the reservation, in the month it was made."""
        with scoped_transaction(self._engine, user_id=reservation.user_id) as connection:
            connection.execute(
                sa.text(
                    "UPDATE ai_budget_months SET"
                    " reserved = greatest(reserved - :amount, 0), spent = spent + :cost"
                    f" WHERE {OWN} AND month = :month"
                ),
                {
                    "user": reservation.user_id,
                    "month": reservation.month,
                    "amount": reservation.amount,
                    "cost": cost,
                },
            )
