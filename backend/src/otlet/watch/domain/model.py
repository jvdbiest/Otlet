# SPDX-License-Identifier: AGPL-3.0-or-later
"""Topics and the lexical score of an item for a topic, free of any framework (U02,
F-VEI-01, F-VEI-02, ARCHITECTURE §13.3).

The score is explainable by construction: it is the sum of the contributions listed in its
explanation, and each contribution names the term and where it was found. Matching ignores
case and accents, accepts a plural in -s or -x, a phrase in quotes or of several words, and a
prefix ending in *. An exclusion found anywhere removes the item from the topic.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

NAME_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 2000
TERM_MAX_LENGTH = 100
TERMS_MAX = 50
# Languages a topic can be limited to (BCP 47 primary subtags).
LANGUAGES = ("fr", "en", "de", "nl", "es", "it", "pt")

TITLE_POINTS = 3  # a term in the title
TEXT_POINTS = 1  # each occurrence in the summary or the text…
TEXT_OCCURRENCES_MAX = 3  # …counted up to this number
SOURCE_POINTS = 1  # an item of a source whose every item belongs to the topic
# Freshness, added when the topic's items are listed: it changes with time, the rest does not.
FRESH_POINTS = ((timedelta(hours=24), 2), (timedelta(hours=72), 1))

WORD = re.compile(r"\w+")


class WatchError(Exception):
    """A rule of the watch module was not met. `code` is stable and translated by the
    interface; the message explains it in English."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Topic:
    id: UUID
    workspace_id: UUID
    name: str
    description: str
    keywords: tuple[str, ...]
    exclusions: tuple[str, ...]
    languages: tuple[str, ...]
    source_ids: tuple[UUID, ...]
    created_at: datetime
    item_count: int = 0
    # Every item of the targeted sources belongs to the topic; keywords then only add points.
    whole_sources: bool = False
    # The last request to match the topic again, and the request its matches answer.
    rescore_requested_at: datetime | None = None
    rescored_at: datetime | None = None

    @property
    def rescoring(self) -> bool:
        if self.rescore_requested_at is None:
            return False
        return self.rescored_at is None or self.rescored_at < self.rescore_requested_at


@dataclass(frozen=True, slots=True)
class Contribution:
    """One line of an explanation: `term` found `count` times in `where`, worth `points`."""

    term: str
    where: str  # "title", "text", or "source" (the item comes from a targeted source)
    count: int
    points: int


@dataclass(frozen=True, slots=True)
class Match:
    score: int
    contributions: tuple[Contribution, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    """What the score reads of an item."""

    title: str
    text: str  # summary and usable text
    language: str | None
    source_id: UUID | None


@dataclass(frozen=True, slots=True)
class Term:
    """A keyword or an exclusion, as words to find in a row."""

    label: str
    words: tuple[str, ...]
    prefix: bool = False  # the last word may continue (written with a final *)

    @classmethod
    def parse(cls, raw: str) -> "Term | None":
        label = " ".join(raw.strip().strip('"').split())
        prefix = label.endswith("*")
        words = tuple(stem(word) for word in tokens(label.rstrip("*")))
        if not words:
            return None
        return cls(label=label, words=words, prefix=prefix)

    def count_in(self, words: list[str]) -> int:
        size = len(self.words)
        found = 0
        for start in range(len(words) - size + 1):
            window = words[start : start + size]
            head, last = window[:-1], window[-1]
            if list(self.words[:-1]) != head:
                continue
            if last == self.words[-1] or (self.prefix and last.startswith(self.words[-1])):
                found += 1
        return found


def fold(text: str) -> str:
    """Lower case without accents: « Élection » and « election » are the same word."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokens(text: str) -> list[str]:
    return WORD.findall(fold(text))


def stem(word: str) -> str:
    """A plural in -s or -x and its singular are the same word (élections, élection)."""
    if len(word) > 3 and word[-1] in "sx" and not word.endswith("ss"):
        return word[:-1]
    return word


def words_of(text: str) -> list[str]:
    return [stem(word) for word in tokens(text)]


def _unique(raw: tuple[str, ...]) -> tuple[Term, ...]:
    """The parsed terms, once each: two spellings of the same words count once."""
    found: dict[tuple[tuple[str, ...], bool], Term] = {}
    for term in map(Term.parse, raw):
        if term is not None:
            found.setdefault((term.words, term.prefix), term)
    return tuple(found.values())


@dataclass(frozen=True, slots=True)
class Rules:
    """The parsed terms of a topic, ready to score many items."""

    keywords: tuple[Term, ...]
    exclusions: tuple[Term, ...]
    languages: tuple[str, ...] = ()
    source_ids: frozenset[UUID] = field(default_factory=frozenset)
    whole_sources: bool = False

    @classmethod
    def of(cls, topic: Topic) -> "Rules":
        return cls(
            keywords=_unique(topic.keywords),
            exclusions=_unique(topic.exclusions),
            languages=topic.languages,
            source_ids=frozenset(topic.source_ids),
            whole_sources=topic.whole_sources and bool(topic.source_ids),
        )

    def match(self, candidate: Candidate) -> Match | None:
        """The match of an item with the topic, or None when it does not belong to it."""
        if self.source_ids and candidate.source_id not in self.source_ids:
            return None
        if self.languages:
            primary = (candidate.language or "").lower().split("-")[0]
            if primary not in self.languages:
                return None
        title, text = words_of(candidate.title), words_of(candidate.text)
        if any(term.count_in(title) or term.count_in(text) for term in self.exclusions):
            return None
        contributions = []
        if self.whole_sources:
            contributions.append(Contribution("", "source", 1, SOURCE_POINTS))
        for term in self.keywords:
            if term.count_in(title):
                contributions.append(Contribution(term.label, "title", 1, TITLE_POINTS))
            found = min(term.count_in(text), TEXT_OCCURRENCES_MAX)
            if found:
                contributions.append(Contribution(term.label, "text", found, found * TEXT_POINTS))
        if not contributions:
            return None
        return Match(sum(c.points for c in contributions), tuple(contributions))


def freshness_points(age: timedelta) -> int:
    return next((points for limit, points in FRESH_POINTS if age < limit), 0)


def check_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not 1 <= len(cleaned) <= NAME_MAX_LENGTH:
        raise WatchError("invalid_name", f"a topic name has 1 to {NAME_MAX_LENGTH} characters")
    return cleaned


def check_description(description: str) -> str:
    cleaned = description.strip()
    if len(cleaned) > DESCRIPTION_MAX_LENGTH:
        raise WatchError(
            "invalid_description",
            f"a description has at most {DESCRIPTION_MAX_LENGTH} characters",
        )
    return cleaned


def check_terms(terms: list[str], *, required: bool) -> tuple[str, ...]:
    # Terms that only differ by case or accents are one term: « élection* » is « election* ».
    unique: dict[str, str] = {}
    for term in terms:
        label = " ".join(term.split())
        if label:
            unique.setdefault(fold(label), label)
    cleaned = list(unique.values())
    if required and not cleaned:
        raise WatchError("no_keywords", "a topic needs at least one keyword")
    if len(cleaned) > TERMS_MAX:
        raise WatchError("too_many_terms", f"at most {TERMS_MAX} keywords or exclusions")
    if any(len(t) > TERM_MAX_LENGTH for t in cleaned):
        raise WatchError("term_too_long", f"a term has at most {TERM_MAX_LENGTH} characters")
    if any(Term.parse(t) is None for t in cleaned):
        raise WatchError("invalid_terms", "a term needs at least one letter or digit")
    return tuple(cleaned)


def check_whole_sources(whole_sources: bool, source_ids: tuple[UUID, ...]) -> bool:
    if whole_sources and not source_ids:
        raise WatchError("no_sources", "every item of the sources needs at least one source")
    return whole_sources


def check_languages(languages: list[str]) -> tuple[str, ...]:
    cleaned = tuple(dict.fromkeys(language.strip().lower() for language in languages))
    if any(language not in LANGUAGES for language in cleaned):
        raise WatchError("invalid_languages", f"languages are among {', '.join(LANGUAGES)}")
    return cleaned
