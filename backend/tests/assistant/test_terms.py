# SPDX-License-Identifier: AGPL-3.0-or-later
"""The terms of a subject and the glossary that widens them (ADR-0043)."""

import pytest

from otlet.assistant.domain.fusion import widely_near
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


def test_next_to_one_word_a_term_needs_a_real_share_to_be_too_general() -> None:
    """« tempêtes » beside « intempéries » is a synonym; « cyberattaque » beside « piratage de
    Binance » widens a precise subject (Joël, 2026-10-30)."""
    from otlet.assistant.domain.terms import Widened, too_general

    weather = Widened(Concept("intempéries", ("intempéries", "tempêtes")), ())
    assert too_general([weather], {"intempéries": 9, "tempêtes": 52}, 2360)[0].general == ()
    binance = Widened(Concept("Binance", ("piratage de Binance", "cyberattaque")), ())
    counts = {"piratage de Binance": 7, "cyberattaque": 57}
    assert too_general([binance], counts, 2360)[0].general == ("cyberattaque",)
    strike = Widened(Concept("grève", ("grève", "transport")), ())
    assert too_general([strike], {"grève": 27, "transport": 169}, 2360)[0].general == ("transport",)


def test_the_reporter_reads_under_the_floor_below_a_best_item() -> None:
    """The cold of Joël (2026-11-01): the best at 0.63, the answers down to 0.43."""
    scored = [("a", 0.63), ("b", 0.53), ("c", 0.43), ("d", 0.37)]
    assert widely_near(scored) == ["a", "b", "c"]
    # A best item under 0.55: the Veille has nothing on it.
    assert widely_near([("a", 0.54), ("b", 0.5)]) == []
    assert widely_near([]) == []
    # A precise question: the floor follows the best item.
    assert widely_near([("a", 0.77), ("b", 0.55), ("c", 0.43)]) == ["a", "b"]
    # Above the floor of ADR-0045, past the first 30 too; under it, not.
    high = [(n, 0.7) for n in range(40)]
    assert len(widely_near(high)) == 40
    low = [("a", 0.7), *((n, 0.5) for n in range(40))]
    assert len(widely_near(low)) == 30
