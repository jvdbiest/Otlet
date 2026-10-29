# SPDX-License-Identifier: AGPL-3.0-or-later
"""The terms of a subject and the glossary that widens them (ADR-0043)."""

import pytest

from otlet.assistant.domain.terms import (
    Concept,
    GlossaryEntry,
    TermsError,
    checked_concepts,
    checked_entry,
    publisher_country,
    websearch,
    widen,
)

BRUSSELS = GlossaryEntry(
    ("Bruxelles-Capitale", "Brussels Hoofdstedelijk Gewest", "Brussels-Capital Region", "Brussel")
)
BUDGET = GlossaryEntry(("budget", "begroting"))


def test_the_glossary_brings_the_other_languages() -> None:
    """The budget of Brussels on the bench: none of the Dutch items without the glossary."""
    concepts = [Concept("budget", ("budget",)), Concept("Bruxelles", ("bruxelles-capitale",))]
    widened = widen(concepts, [BRUSSELS, BUDGET, GlossaryEntry(("loyer", "huur"))])
    assert widened[0].added == ("begroting",)
    # The match is case and accent blind; the term already there is not added again.
    assert widened[1].added == (
        "Brussels Hoofdstedelijk Gewest",
        "Brussels-Capital Region",
        "Brussel",
    )
    assert widened[1].terms[0] == "bruxelles-capitale"


def test_a_concept_without_entry_keeps_its_terms() -> None:
    widened = widen([Concept("Austen", ("Austen",))], [BUDGET])
    assert (widened[0].terms, widened[0].added) == (("Austen",), ())


def test_the_concepts_are_checked() -> None:
    clean = checked_concepts([Concept("  tempête ", ("tempête", " Tempête ", "storm", ""))])
    assert clean == [Concept("tempête", ("tempête", "storm"))]
    with pytest.raises(TermsError, match="1 to 2 concepts"):
        checked_concepts([Concept("a", ("a",))] * 3)
    with pytest.raises(TermsError) as refused:
        checked_concepts([Concept("a", ("",))])
    assert refused.value.code == "invalid_terms"


def test_an_entry_holds_two_terms_at_least() -> None:
    assert checked_entry([" budget ", "begroting", "Budget"]) == ("budget", "begroting")
    with pytest.raises(TermsError):
        checked_entry(["budget"])


def test_a_term_holds_all_its_words_and_no_operator() -> None:
    assert websearch("Région de Bruxelles-Capitale") == "Région de Bruxelles-Capitale"
    assert websearch('budget "bruxellois" or -dette -') == "budget bruxellois dette"
    # A term between quotes as a whole is a phrase (« "GTA VI" », Joël, 2026-10-29).
    assert websearch('"GTA VI"') == '"GTA VI"'


def test_the_country_of_a_publisher_comes_from_its_address() -> None:
    assert publisher_country("https://www.dhnet.be/actu/x") == "Belgique"
    assert publisher_country("https://www.lemonde.fr/x") == "France"
    assert publisher_country("https://www.01net.com/x") is None
    assert publisher_country(None) is None


def test_a_term_too_general_is_set_aside_but_shown() -> None:
    """Bench of A2: « course » found 752 items of 2,940; « Bruxelles », 265 in a concept
    « Austen » of 50. The first term of a concept always stays."""
    from otlet.assistant.domain.terms import Widened, too_general

    concepts = [
        Widened(Concept("Austen", ("Austen", "tempête Austen", "Bruxelles", "course")), ()),
        Widened(Concept("Bruxelles", ("Bruxelles", "bruxellois")), ()),
    ]
    counts = {"Austen": 50, "tempête Austen": 45, "Bruxelles": 265, "bruxellois": 94, "course": 752}
    checked = too_general(concepts, counts, 2940)
    assert checked[0].general == ("Bruxelles", "course")
    assert checked[0].terms == ("Austen", "tempête Austen")
    assert checked[0].all_terms == ("Austen", "tempête Austen", "Bruxelles", "course")
    assert checked[1].general == ()  # 265 of 2,940 is under 10 %, and it leads its concept
