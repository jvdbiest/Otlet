# SPDX-License-Identifier: AGPL-3.0-or-later
"""The monthly budget of a user, with reservation (ADR-0027 §3).

Before each call, the gateway reserves the most the call may cost; the reservation is refused
when what is spent, plus what is reserved, plus this call would go beyond the limit minus a
guard band of 10 %, kept for providers that charge more than announced. After the call, the
real cost replaces the reservation. The check and the reservation are one conditional update
of one row in the database: concurrent calls cannot overrun it (S4, criterion C2).

The limit is the user's: by default 0, so only free models (local engines) run until the user
sets a budget for paid ones.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

GUARD_BAND = Decimal("0.10")
LIMIT_MAX = Decimal(100_000)


def month_of(moment: datetime) -> date:
    return date(moment.year, moment.month, 1)


@dataclass(frozen=True, slots=True)
class Reservation:
    user_id: UUID
    month: date
    amount: Decimal


@dataclass(frozen=True, slots=True)
class BudgetState:
    month: date
    limit: Decimal
    spent: Decimal
    reserved: Decimal

    @property
    def usable(self) -> Decimal:
        """What may still be reserved this month, guard band deducted."""
        return max(Decimal(0), self.limit * (1 - GUARD_BAND) - self.spent - self.reserved)


def check_limit(limit: Decimal) -> Decimal:
    if not Decimal(0) <= limit <= LIMIT_MAX:
        raise ValueError(f"a monthly budget is between 0 and {LIMIT_MAX}")
    return limit.quantize(Decimal("0.01"))
