# SPDX-License-Identifier: AGPL-3.0-or-later
"""Triage of the watch feed (X02, F-VEI-04, F-VEI-05): keep, dismiss, pin, read."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Decision(StrEnum):
    KEPT = "kept"  # retained: the briefs of I2 start from these
    DISMISSED = "dismissed"
    ARCHIVED = "archived"  # done with: out of the current views, still searchable


class View(StrEnum):
    """The parts of the feed a user looks at."""

    TO_SORT = "to_sort"  # no decision yet: the default
    KEPT = "kept"
    DISMISSED = "dismissed"
    ARCHIVED = "archived"
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


@dataclass(frozen=True, slots=True)
class TopicFilter:
    """Items of the chosen topics: of at least one, or of every one when `all_topics`."""

    topic_ids: tuple[UUID, ...] = ()
    all_topics: bool = False


NO_TOPIC_FILTER = TopicFilter()


@dataclass(frozen=True, slots=True)
class TopicTag:
    """A topic an item matches. Tags come best score first: the first is the main topic."""

    id: UUID
    name: str
    score: int


@dataclass(frozen=True, slots=True)
class Period:
    """Items dated from `since` (included) to `until` (excluded); None leaves that side open.
    The interface computes the bounds (today, this week, this month) in the user's time zone."""

    since: datetime | None = None
    until: datetime | None = None

    @property
    def valid(self) -> bool:
        return self.since is None or self.until is None or self.since < self.until


ANY_TIME = Period()


class Sort(StrEnum):
    """How the feed is ordered (U03); pinned items stay first in the views that pin them."""

    DATE = "date"  # the most recent first: the default
    SCORE = "score"  # the best score of the item first, then the date
    TOPIC = "topic"  # by main topic, in alphabetical order, then the date; no topic last
    SOURCE = "source"  # by source, in alphabetical order, then the date; manual entries last


class GroupBy(StrEnum):
    TOPIC = "topic"  # the main topic of each item: an item is in one group only
    SOURCE = "source"


@dataclass(frozen=True, slots=True)
class Group:
    """One group of the feed: `key` is None for the items without topic (or without source)."""

    key: UUID | None
    name: str
    count: int


@dataclass(frozen=True, slots=True)
class InGroup:
    """Keeps the items of one group of the feed."""

    by: GroupBy
    key: UUID | None
