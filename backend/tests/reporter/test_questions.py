# SPDX-License-Identifier: AGPL-3.0-or-later
"""A question as an operation, kept to what the question says (ADR-0044 §3, §4)."""

import json

from otlet.assistant.domain.terms import Concept
from otlet.reporter.domain.questions import (
    Operation,
    State,
    Translated,
    check_operation,
    guarded,
    next_state,
    read_operation,
)

AUSTEN = Concept("tempête Austen", ("tempête Austen", "storm Austen", "Austen"))
BXL = Concept("Bruxelles", ("Bruxelles", "Brussel"))


def answer(operation: str, *concepts: tuple[str, list[str]], langue: str | None = None) -> str:
    return json.dumps(
        {
            "operation": operation,
            "concepts": [{"name": n, "terms": t} for n, t in concepts],
            "langue": langue,
        }
    )


def test_an_answer_is_read_and_cleaned() -> None:
    raw = answer("chercher", ("Austen", [" tempête  Austen", "Austen", "austen", ""]))
    assert check_operation(raw) == []
    assert read_operation(raw) == Translated(
        Operation.CHERCHER, (Concept("Austen", ("tempête Austen", "Austen")),), None
    )
    assert check_operation('{"operation": "deviner", "concepts": []}')
    assert check_operation("pas du json")


def test_only_three_languages_are_languages() -> None:
    """The model answered « toutes »: taken for a language, it emptied every set (bench)."""
    assert read_operation(answer("restreindre", langue="toutes")).language is None
    assert read_operation(answer("restreindre", langue="nl")).language == "nl"


def test_a_concept_the_question_does_not_name_is_dropped() -> None:
    """Bench, conversation 3: « Quel impact sur la ville ? » gave a concept « impact, effet »."""
    translated = Translated(
        Operation.RESTREINDRE,
        (
            Concept("impact", ("impact", "effet", "conséquence")),
            Concept("Bruxelles", ("Bruxelles",)),
        ),
        None,
    )
    kept = guarded("Lesquels concernent Bruxelles ?", translated)
    assert kept.concepts == (Concept("Bruxelles", ("Bruxelles",)),)


def test_a_search_keeps_its_first_concept_when_none_is_named() -> None:
    translated = Translated(Operation.CHERCHER, (AUSTEN, BXL), None)
    assert guarded("La tempête de vendredi", translated).concepts == (AUSTEN,)


def test_a_language_asked_is_a_filter() -> None:
    translated = Translated(Operation.CHERCHER, (Concept("néerlandais", ("néerlandais",)),), None)
    assert guarded("Et en néerlandais ?", translated) == Translated(Operation.RESTREINDRE, (), "nl")


def test_the_state_follows_the_operations() -> None:
    state = next_state(State(), Translated(Operation.CHERCHER, (AUSTEN,), None))
    state = next_state(state, Translated(Operation.RESTREINDRE, (), "nl"))
    assert state == State((AUSTEN,), "nl")
    state = next_state(state, Translated(Operation.RESTREINDRE, (BXL,), None))
    assert state == State((AUSTEN, BXL), "nl")
    state = next_state(state, Translated(Operation.ELARGIR, (Concept("x", ("Brussels",)),), None))
    assert state.concepts[-1].terms == ("Bruxelles", "Brussel", "Brussels")
    # A fact or a sort does not change the set; a new search starts in every language.
    assert next_state(state, Translated(Operation.FAIT, (), None)) == state
    assert next_state(state, Translated(Operation.CHERCHER, (BXL,), None)) == State((BXL,), None)


def test_a_period_named_is_a_filter() -> None:
    """« les actualités de piratage de ces derniers jours » kept 30 days (Joël, 2026-10-25)."""
    from otlet.reporter.domain.questions import asked_period

    assert asked_period("quels sont les actualités de piratage de ces derniers jours ?") == 7
    assert asked_period("La météo du jour en Belgique ?") == 1
    assert asked_period("Tempête Austen") is None
    concept = Concept("piratage", ("piratage",))
    translated = guarded(
        "Le piratage de ces derniers jours", Translated(Operation.CHERCHER, (concept,), None)
    )
    assert translated.days == 7
    assert next_state(State(), translated) == State((concept,), None, 7)


def test_a_period_names_no_concept_and_a_named_subject_is_searched() -> None:
    """« Quel sont les dernières actualités des jeux vidéo cette semaine ? » (Joël, 2026-10-25):
    a concept « semaine, week », then « jeux vidéo » searched by « console, PC, mobile »."""
    question = "Quel sont les dernières actualités des jeux vidéo cette semaine ?"
    week = Concept("semaine", ("semaine", "week"))
    games = Concept("jeux vidéo", ("nouveau jeu", "console", "PC"))
    kept = guarded(question, Translated(Operation.CHERCHER, (week, games), None))
    assert kept.concepts == (Concept("jeux vidéo", ("jeux vidéo", "nouveau jeu", "console", "PC")),)
    assert kept.days == 7
    only_week = guarded(question, Translated(Operation.CHERCHER, (week,), None))
    assert only_week.concepts == () and only_week.days == 7
