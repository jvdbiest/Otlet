# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sources, items and their legal status, free of any framework (U01, RISKS M-08)."""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

NAME_MAX_LENGTH = 200
URL_MAX_LENGTH = 2000
# Bounds of the collection frequency set by the instance (F-SRC-06, CO-09).
INTERVAL_MIN_MINUTES = 15
INTERVAL_MAX_MINUTES = 7 * 24 * 60
INTERVAL_DEFAULT_MINUTES = 60
# Health of a source (F-SRC-09): degraded after a few failures in a row, dead after many.
DEGRADED_AFTER_FAILURES = 3
DEAD_AFTER_FAILURES = 10
# Manual entry (F-SRC-04, M-08).
TITLE_MAX_LENGTH = 500
MANUAL_TEXT_MAX_LENGTH = 200_000
DECLARATION_MIN_LENGTH = 3
DECLARATION_MAX_LENGTH = 1000
# Tracking parameters dropped from item URLs, so that the same article is recognised.
TRACKING_PREFIXES = ("utm_", "mc_")
TRACKING_PARAMETERS = frozenset({"fbclid", "gclid", "igshid", "ref_src"})


class CollectionError(Exception):
    """A rule of the collection module was not met. `code` is stable and translated by the
    interface; the message explains it in English for the logs and the API."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class LegalStatus(StrEnum):
    """What Otlet may do with the texts of a source (M-08), stored as its value.

    - full_text: the pages may be read and their text used;
    - summary_only: only what the feed itself gives (title, link, summary) is kept, because the
      site reserves text and data mining or its robots.txt closes the pages;
    - refused: the feed itself may not be collected;
    - unknown: not checked yet.
    """

    FULL_TEXT = "full_text"
    SUMMARY_ONLY = "summary_only"
    REFUSED = "refused"
    UNKNOWN = "unknown"


class TextStatus(StrEnum):
    """Where the text of an item comes from, and what it may be used for."""

    PENDING = "pending"  # the page has not been read yet
    FULL_TEXT = "full_text"
    SUMMARY_ONLY = "summary_only"
    MANUAL = "manual"  # pasted by the user, with a declared origin and right of use


class Origin(StrEnum):
    FEED = "feed"
    MANUAL_URL = "manual_url"
    MANUAL_TEXT = "manual_text"


class Health(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DEAD = "dead"


@dataclass(frozen=True, slots=True)
class Decision:
    """The outcome of a compliance check, with a stable reason code shown to the user and kept
    in the compliance journal of the source (CJ-03)."""

    allowed: bool
    reason: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Source:
    id: UUID
    workspace_id: UUID
    name: str
    url: str  # as the user entered it
    feed_url: str
    site_url: str | None
    interval_minutes: int
    active: bool
    legal_status: LegalStatus
    legal_reason: str | None
    created_at: datetime
    last_fetched_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    next_fetch_at: datetime | None
    item_count: int = 0

    @property
    def health(self) -> Health:
        return health(self.consecutive_failures)


@dataclass(frozen=True, slots=True)
class Item:
    id: UUID
    workspace_id: UUID
    source_id: UUID | None
    source_name: str | None
    origin: Origin
    url: str | None
    title: str
    author: str | None
    published_at: datetime | None
    collected_at: datetime
    summary: str | None
    text: str | None
    text_status: TextStatus
    text_reason: str | None
    declared_origin: str | None
    usage_right: str | None
    duplicates: int = 0  # other items of the same story (U02)


# Declarations of rights (Joël, 2026-10-20): the bases a person may give, and the commitment
# they accept, kept word for word with each declaration.
RIGHTS_BASES = ("publisher_agreement", "licence", "own_content", "other")
RIGHTS_COMMITMENT = (
    "Je certifie disposer des droits ou autorisations nécessaires pour importer et exploiter ce"
    " contenu dans Otlet. J'assume l'entière responsabilité de son utilisation."
)
DECLARED_RIGHTS = "declared_rights"  # the text reason of a text read under a declaration
RIGHTS_DETAIL_MAX = 500


def reserved(reason: str | None) -> bool:
    """A text the publisher reserves from text mining: only a declaration of rights opens it."""
    return reason is not None and reason.startswith("tdm_reserved")


@dataclass(frozen=True, slots=True)
class RightsDeclaration:
    id: UUID
    item_id: UUID
    declared_by: UUID
    basis: str
    detail: str
    reference: str
    commitment: str
    declared_at: datetime


def retryable(reason: str | None) -> bool:
    """A text missed for a technical reason, which reading the page again may fix (Joël,
    2026-10-20); never a refusal of the site (robots.txt, a reservation of text mining)."""
    if reason is None:
        return False
    return reason in ("no_text_found", "not_html") or reason.startswith(("http_", "fetch_"))


@dataclass(frozen=True, slots=True)
class Check:
    """An entry of a source's compliance journal."""

    checked_at: datetime
    url: str
    allowed: bool
    reason: str
    detail: str


def health(consecutive_failures: int) -> Health:
    if consecutive_failures >= DEAD_AFTER_FAILURES:
        return Health.DEAD
    if consecutive_failures >= DEGRADED_AFTER_FAILURES:
        return Health.DEGRADED
    return Health.OK


def check_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not 1 <= len(cleaned) <= NAME_MAX_LENGTH:
        raise CollectionError(
            "invalid_name", f"a source name has 1 to {NAME_MAX_LENGTH} characters"
        )
    return cleaned


def check_interval(minutes: int) -> int:
    if not INTERVAL_MIN_MINUTES <= minutes <= INTERVAL_MAX_MINUTES:
        raise CollectionError(
            "invalid_interval",
            f"the collection interval is between {INTERVAL_MIN_MINUTES} minutes"
            f" and {INTERVAL_MAX_MINUTES // (24 * 60)} days",
        )
    return minutes


def next_fetch_delay(interval_minutes: int, consecutive_failures: int) -> timedelta:
    """The interval, doubled at each failure in a row, within the bounds of the instance: a
    broken source is retried less and less often but never abandoned."""
    factor = 2 ** min(consecutive_failures, 10)
    return timedelta(minutes=min(interval_minutes * factor, INTERVAL_MAX_MINUTES))


def check_url(url: str) -> str:
    """A URL a user typed, trimmed, with https:// added when the scheme is missing. Whether it
    may be fetched is decided by the HTTP client (SSRF) and the compliance checks."""
    cleaned = url.strip()
    if "://" not in cleaned:
        cleaned = "https://" + cleaned
    parts = urlsplit(cleaned)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise CollectionError(
            "invalid_url", "enter a web address starting with http:// or https://"
        )
    if len(cleaned) > URL_MAX_LENGTH:
        raise CollectionError(
            "invalid_url", f"a web address has at most {URL_MAX_LENGTH} characters"
        )
    return cleaned


def normalize_url(url: str) -> str:
    """The form used to recognise an item: lower-case scheme and host, no default port, no
    fragment, no tracking parameters, remaining parameters sorted."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    port = parts.port
    if port is not None and (parts.scheme, port) not in (("http", 80), ("https", 443)):
        host = f"{host}:{port}"
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(TRACKING_PREFIXES) and key.lower() not in TRACKING_PARAMETERS
    )
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(query), ""))


def check_declaration(value: str, what: str) -> str:
    cleaned = " ".join(value.split())
    if not DECLARATION_MIN_LENGTH <= len(cleaned) <= DECLARATION_MAX_LENGTH:
        raise CollectionError(
            "invalid_declaration",
            f"the {what} has {DECLARATION_MIN_LENGTH} to {DECLARATION_MAX_LENGTH} characters",
        )
    return cleaned


def check_manual_text(title: str, text: str) -> tuple[str, str]:
    cleaned_title = " ".join(title.split())
    if not 1 <= len(cleaned_title) <= TITLE_MAX_LENGTH:
        raise CollectionError("invalid_title", f"a title has 1 to {TITLE_MAX_LENGTH} characters")
    cleaned_text = unicodedata.normalize("NFC", text).strip()
    if not 1 <= len(cleaned_text) <= MANUAL_TEXT_MAX_LENGTH:
        raise CollectionError(
            "invalid_text", f"a pasted text has 1 to {MANUAL_TEXT_MAX_LENGTH} characters"
        )
    return cleaned_title, cleaned_text


@dataclass(frozen=True, slots=True)
class FeedEntry:
    """An entry of a feed, its texts already sanitised and reduced to plain text."""

    guid: str
    url: str | None
    title: str
    author: str | None
    published_at: datetime | None
    summary: str | None
    content: str | None  # the full text the feed itself carries, when it does
    language: str | None = None  # as the feed declares it (BCP 47, such as fr or en-GB)


@dataclass(frozen=True, slots=True)
class ParsedFeed:
    title: str | None
    site_url: str | None
    entries: tuple[FeedEntry, ...]
    language: str | None = None


@dataclass(frozen=True, slots=True)
class Page:
    """The main content of an article page."""

    title: str | None
    text: str
    language: str | None = None


# Text search configurations of PostgreSQL, by language (BCP 47 primary subtag). Other
# languages are indexed without stemming ("simple").
SEARCH_CONFIGS = {
    "fr": "french",
    "en": "english",
    "de": "german",
    "nl": "dutch",
    "es": "spanish",
    "it": "italian",
    "pt": "portuguese",
}
SIMPLE_SEARCH = "simple"


def search_config(language: str | None) -> str:
    primary = (language or "").strip().lower().replace("_", "-").split("-")[0]
    return SEARCH_CONFIGS.get(primary, SIMPLE_SEARCH)


# Frequent short words of each language that has its own search configuration: enough to
# tell the language of a text that declares none. A topic limited to some languages would
# otherwise miss the item, and its search would not be stemmed.
STOP_WORDS = {
    "fr": frozenset(
        "le la les des un une est et du qui dans pour pas sur au aux avec ce cette il elle sont"
        " ont mais plus nous vous leur".split()
    ),
    "en": frozenset(
        "the and of to is that for it with as was on are by this be at from have has were"
        " which their will".split()
    ),
    "de": frozenset(
        "der die das und ist nicht ein eine zu den von mit sich des auf für im dem auch es"
        " wird sind".split()
    ),
    "nl": frozenset(
        "het een en van is dat op te voor niet met zijn er aan ook als bij werd door naar".split()
    ),
    "es": frozenset(
        "el los las del y que una por con para no se al lo como más pero sus fue está".split()
    ),
    "it": frozenset(
        "il di che è della delle degli gli per non con sono da anche nel alla questo".split()
    ),
    "pt": frozenset(
        "o os do da dos das em um uma para com não é na no por mais que foi são".split()
    ),
}
GUESS_MIN_HITS = 5  # frequent words found, below which the text is too short to tell
GUESS_MARGIN = 1.5  # the first language must lead the second by this factor
_WORD = re.compile(r"\w+")


def guess_language(text: str) -> str | None:
    """The language of a text that declares none, from its frequent words, or None when the
    text is too short or too mixed to tell."""
    hits = Counter(
        language
        for word in _WORD.findall(text.lower())
        for language, words in STOP_WORDS.items()
        if word in words
    ).most_common(2)
    if not hits or hits[0][1] < GUESS_MIN_HITS:
        return None
    if len(hits) == 2 and hits[0][1] < GUESS_MARGIN * hits[1][1]:
        return None
    return hits[0][0]


def clean_language(language: object) -> str | None:
    """A language tag as declared by a feed or a page, kept when it looks like one."""
    if not isinstance(language, str):
        return None
    tag = language.strip().replace("_", "-")[:35]
    return tag if tag and all(part.isalnum() for part in tag.split("-")) else None
