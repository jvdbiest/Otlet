# SPDX-License-Identifier: AGPL-3.0-or-later
"""The terms of a subject, and the glossary that widens them (ADR-0043): what the Assistant de
veille searches, shown to the author before the search, with no model in the search itself.

A subject is one or two concepts; an item is a candidate when it holds a term of every concept,
in any language of the index. The glossary of the workspace holds terms that mean the same
(« Bruxelles-Capitale », « Brussels Hoofdstedelijk Gewest », « Brussels-Capital Region »): a
term of an entry brings the others. On the bench of A1b it found all the matter the current
search missed, Dutch included.
"""

import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

CONCEPTS_MAX = 2
TERMS_MAX = 20
TERM_MAX_LENGTH = 80
ENTRY_TERMS = (2, 30)


class TermsError(Exception):
    """A rule of the terms or of the glossary was not met; `code` is stable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def folded(term: str) -> str:
    """How terms are compared: case, accents and spacing aside."""
    text = unicodedata.normalize("NFKD", term.casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def _clean(terms: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """The terms trimmed, without empties and repeats (as folded), in their order."""
    seen: dict[str, str] = {}
    for term in terms:
        text = " ".join(term.split())
        if text and folded(text) not in seen:
            seen[folded(text)] = text
    return tuple(seen.values())


@dataclass(frozen=True, slots=True)
class Concept:
    name: str
    terms: tuple[str, ...]


def checked_concepts(concepts: list[Concept]) -> list[Concept]:
    """The concepts trimmed, or a TermsError naming the first rule they break."""
    if not 1 <= len(concepts) <= CONCEPTS_MAX:
        raise TermsError("invalid_concepts", f"a subject has 1 to {CONCEPTS_MAX} concepts")
    out = []
    for concept in concepts:
        terms = _clean(concept.terms)
        if not 1 <= len(terms) <= TERMS_MAX:
            raise TermsError("invalid_terms", f"a concept has 1 to {TERMS_MAX} terms")
        if any(len(term) > TERM_MAX_LENGTH for term in terms):
            raise TermsError("invalid_terms", f"a term has at most {TERM_MAX_LENGTH} characters")
        out.append(Concept(" ".join(concept.name.split())[:TERM_MAX_LENGTH], terms))
    return out


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    """Terms that mean the same thing, in one or several languages."""

    terms: tuple[str, ...]


def checked_entry(terms: list[str]) -> tuple[str, ...]:
    clean = _clean(terms)
    low, high = ENTRY_TERMS
    if not low <= len(clean) <= high or any(len(t) > TERM_MAX_LENGTH for t in clean):
        raise TermsError(
            "invalid_entry", f"an entry has {low} to {high} terms of {TERM_MAX_LENGTH} characters"
        )
    return clean


@dataclass(frozen=True, slots=True)
class Widened:
    """A concept with the terms the glossary adds to it, kept apart to be shown as such."""

    concept: Concept
    added: tuple[str, ...]
    # Terms set aside as too general (too_general): shown, never searched.
    general: tuple[str, ...] = ()

    @property
    def all_terms(self) -> tuple[str, ...]:
        return (*self.concept.terms, *self.added)

    @property
    def terms(self) -> tuple[str, ...]:
        """The terms searched: all but the general ones."""
        return tuple(term for term in self.all_terms if term not in self.general)


def widen(concepts: list[Concept], glossary: list[GlossaryEntry]) -> list[Widened]:
    """Each concept with the terms of every glossary entry that shares one of its terms."""
    out = []
    for concept in concepts:
        known = {folded(term) for term in concept.terms}
        added: list[str] = []
        for entry in glossary:
            if known & {folded(term) for term in entry.terms}:
                for term in entry.terms:
                    if folded(term) not in known:
                        known.add(folded(term))
                        added.append(term)
        out.append(Widened(concept, tuple(added)))
    return out


def websearch(term: str) -> str:
    """A term as a query of websearch_to_tsquery: all its words, in any order. Its operators
    are taken out (quotes, a leading « - », the word « or »): a term is never a query."""
    words = term.replace('"', " ").split()
    return " ".join(w.lstrip("-") for w in words if w.lower() != "or" and w.lstrip("-"))


# The country of a publisher, from the address of its item (ADR-0043 §5): the model needs it
# for an angle such as « en Belgique », whose items seldom write « Belgique ».
COUNTRIES = {
    "be": "Belgique",
    "fr": "France",
    "nl": "Pays-Bas",
    "lu": "Luxembourg",
    "ch": "Suisse",
    "de": "Allemagne",
    "uk": "Royaume-Uni",
    "ca": "Canada",
}


def publisher_country(url: str | None) -> str | None:
    host = urlsplit(url).hostname if url else None
    if not host or "." not in host:
        return None
    return COUNTRIES.get(host.rsplit(".", 1)[1])


# A term is too general when it finds more than this share of the items of the period, or many
# times more than the first term of its concept, the subject's own word (bench of A2, Joël,
# 2026-10-25: « course » found 752 items of 2,940, « Bruxelles » 265 inside a concept
# « Austen » of 50; the sets swelled to 400, then fell to 0).
GENERAL_SHARE = 0.10
GENERAL_RATIO = 4
# Under this many items, a term is never too general: a small Veille has no common words.
GENERAL_MIN = 20


def too_general(concepts: list[Widened], counts: dict[str, int], total: int) -> list[Widened]:
    """The concepts with their too general terms set aside. The first term of a concept is
    never set aside: a concept always keeps something to search."""
    out = []
    for widened in concepts:
        terms = widened.all_terms
        first = counts.get(terms[0], 0)
        general = tuple(
            term
            for term in terms[1:]
            if counts.get(term, 0) >= GENERAL_MIN
            and (
                counts.get(term, 0) > GENERAL_SHARE * total
                or (first > 0 and counts.get(term, 0) > GENERAL_RATIO * first)
            )
        )
        out.append(Widened(widened.concept, widened.added, general))
    return out
