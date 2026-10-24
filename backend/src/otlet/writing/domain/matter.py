# SPDX-License-Identifier: AGPL-3.0-or-later
"""The matter of a brief: what its items hold for an article, judged on five criteria (ADR-0041).

One rule, here: the interface asks for it at each change and keeps no copy. It calls no model:
counts, dates and the words rule of ADR-0038, so a brief always gets the same verdict.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

from otlet.writing.domain.brief import Length, Mode, Nature
from otlet.writing.domain.draft import WORDS, longest_for, matter_level

__all__ = ["Criterion", "Evaluation", "Mark", "MatterItem", "Nature", "evaluate", "publisher"]


class Mark(StrEnum):
    OK = "ok"  # ✓
    WARN = "warn"  # !
    FAIL = "fail"  # ✗


# Starting points (ADR-0041 §2), to recalibrate after use.
SOURCES_OK = 3
PUBLISHERS_OK = 3
FRESH_DAYS = 7
STALE_DAYS = 30


@dataclass(frozen=True, slots=True)
class MatterItem:
    """An item as the matter counts it."""

    id: UUID
    duplicate_of: UUID | None
    publisher: str  # who published it: see publisher()
    dated: datetime  # published, else collected
    words: int  # the words a draft may use of it: a reserved text counts for its summary
    full_text: bool


@dataclass(frozen=True, slots=True)
class Criterion:
    name: str  # sources, publishers, words, freshness, corroboration
    mark: Mark | None  # None: not evaluated yet (corroboration, until A1b or U05)
    value: int | None  # the concrete value: a count, words, days; None when not evaluated
    informative: bool  # shown, no effect on the level
    longest: Length | None = None  # words only: the longest article the matter carries


@dataclass(frozen=True, slots=True)
class Evaluation:
    level: str  # enough, limited, insufficient (the levels of ADR-0038)
    reason: str | None  # the criterion that decides the level; None when it is enough
    criteria: tuple[Criterion, ...]


def publisher(
    source_id: UUID | None, declared_origin: str | None, url: str | None, item_id: UUID
) -> str:
    """Who published an item: the feed it came from; for a pasted text, its declared origin;
    for a page added by hand, its site. Two feeds of one site count as two (to review)."""
    if source_id is not None:
        return f"source:{source_id}"
    if declared_origin and declared_origin.strip():
        return "origin:" + " ".join(declared_origin.lower().split())
    host = urlsplit(url).hostname if url else None
    if host:
        return "site:" + host.removeprefix("www.")
    return f"item:{item_id}"


def _mark(value: int, ok: int, warn: int) -> Mark:
    return Mark.OK if value >= ok else Mark.WARN if value >= warn else Mark.FAIL


def evaluate(
    items: list[MatterItem], length: Length, mode: Mode, nature: Nature, today: date
) -> Evaluation:
    """The five criteria and the level by the hybrid rule (ADR-0041 §3): sources, words and
    publishers block (a ✗ is « insufficient »); with freshness for news, they decide the
    quality (not all ✓ is « limited »); the rest informs."""
    kept: dict[UUID, MatterItem] = {}
    for item in items:  # a duplicate counts once, as the first of its kind in the brief
        kept.setdefault(item.duplicate_of or item.id, item)
    unique = list(kept.values())

    sources = len(unique)
    publishers = len({item.publisher for item in unique})
    words = sum(item.words for item in unique)
    full_text = any(item.full_text for item in unique)
    longest = longest_for(words)
    if not unique or matter_level(words, full_text) == "insufficient":
        words_mark = Mark.FAIL
    elif longest is not None and WORDS[longest] >= WORDS[length]:
        words_mark = Mark.OK
    else:
        words_mark = Mark.WARN
    newest = max((item.dated for item in unique), default=None)
    age = None if newest is None else max((today - newest.date()).days, 0)
    if age is None:
        freshness = Mark.FAIL
    else:
        freshness = Mark.OK if age <= FRESH_DAYS else Mark.WARN if age <= STALE_DAYS else Mark.FAIL

    criteria = (
        Criterion("sources", _mark(sources, SOURCES_OK, 1), sources, False),
        Criterion("publishers", _mark(publishers, PUBLISHERS_OK, 2), publishers, False),
        Criterion("words", words_mark, words, False, longest),
        Criterion("freshness", freshness, age, nature is Nature.BACKGROUND),
        Criterion("corroboration", None, None, mode is Mode.PANORAMA),
    )
    blocking = [c for c in criteria if c.name in ("sources", "words", "publishers")]
    for criterion in blocking:
        if criterion.mark is Mark.FAIL:
            return Evaluation("insufficient", criterion.name, criteria)
    quality = [c for c in criteria if not c.informative and c.mark is not None]
    for mark in (Mark.FAIL, Mark.WARN):
        for criterion in quality:
            if criterion.mark is mark:
                return Evaluation("limited", criterion.name, criteria)
    return Evaluation("enough", None, criteria)
