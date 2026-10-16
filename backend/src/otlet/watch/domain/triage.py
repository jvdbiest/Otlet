# SPDX-License-Identifier: AGPL-3.0-or-later
"""Triage of the watch feed (X02, F-VEI-04, F-VEI-05): keep, dismiss, pin, read."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Decision(StrEnum):
    KEPT = "kept"  # retained: the briefs of I2 start from these
    DISMISSED = "dismissed"


class View(StrEnum):
    """The parts of the feed a user looks at."""

    TO_SORT = "to_sort"  # neither kept nor dismissed: the default
    KEPT = "kept"
    DISMISSED = "dismissed"
    PINNED = "pinned"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class Triage:
    decision: Decision | None = None
    pinned: bool = False
    read_at: datetime | None = None

    @property
    def read(self) -> bool:
        return self.read_at is not None


@dataclass(frozen=True, slots=True)
class Progress:
    """How far a new user went in the first steps (FA §7.7)."""

    sources: int
    topics: int
    decisions: int
