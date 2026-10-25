# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lines of fact cited by source, and the agreement computed without a model (ADR-0044 §5, §6).
The cases are those of the A2 bench (Joël's Veille, 2026-10-25)."""

import json

from otlet.assistant.domain.terms import GlossaryEntry
from otlet.reporter.domain.facts import (
    Agreement,
    Article,
    FactLine,
    concordance,
    read_fact,
    reading_order,
)

BRUSSELS = [GlossaryEntry(("Bruxelles", "Brussel", "Brussels"))]


def line(publisher: str, figure: str, measure: str, when: str, where: str) -> FactLine:
    return FactLine("id", publisher, figure, measure, when, where, figure, True)


def test_four_sources_agree_on_four_injured() -> None:
    """The model said « partiel »; the rule sees four lines that agree, and leaves aside the
    three injured of the city centre, a part of Brussels."""
    agreement, compared = concordance(
        [
            line("La Libre", "4", "blessés", "vendredi", "Bruxelles"),
            line("RTBF", "4", "blessés", "vendredi", "Bruxelles"),
            line("La DH", "3", "blessés", "vendredi", "centre de Bruxelles"),
            line("Bruzz", "4", "gewonden (blessés)", "vendredi", "Brussel"),
        ],
        BRUSSELS,
    )
    assert agreement is Agreement.CONCORDENT
    assert {(c.first, c.second) for c in compared} == {(0, 1), (0, 3), (1, 3)}
    assert all(c.same for c in compared)


def test_two_dates_diverge_and_the_pair_is_shown() -> None:
    """Apple: 28 October at Les Numériques, 27 at 01net; « la semaine prochaine » is vague."""
    agreement, compared = concordance(
        [
            line("Les Numériques", "28 octobre", "date de la présentation", "28 octobre", "LA"),
            line("01net", "la semaine prochaine", "date de la présentation", "non précisé", ""),
            line("01net", "27 octobre", "date de la présentation", "27 octobre", "non précisé"),
        ],
        [],
    )
    assert agreement is Agreement.DIVERGENT
    assert [(c.first, c.second, c.same) for c in compared] == [(0, 2, False)]


def test_one_source_and_no_line() -> None:
    lines = [line("Bruzz", "121", "interventions", "vendredi", "Brussel")]
    lines.append(line("Bruzz", "43", "interventies", "samedi", "Brussel"))
    assert concordance(lines, BRUSSELS)[0] is Agreement.UNE_SOURCE
    assert concordance([], [])[0] is Agreement.ABSENT


def test_different_measures_are_partial() -> None:
    """Liège: 45 arrested, 30 surrounded: not the same measure."""
    agreement, _ = concordance(
        [
            line("La DH", "45", "arrestations", "samedi", "Liège"),
            line("RTBF", "30", "manifestants encerclés", "samedi", "Liège"),
        ],
        [],
    )
    assert agreement is Agreement.PARTIEL


def test_a_line_without_its_passage_is_dropped() -> None:
    articles = [
        Article(
            "a1", "Bruzz", "Actiris schrapt banen. Nog eens 44 werknemers bedreigd met ontslag."
        ),
        Article("a2", "La DH", "Rien sur ce sujet."),
    ]
    raw = json.dumps(
        {
            "lignes": [
                {
                    "article": 1,
                    "chiffre": "44",
                    "mesure": "travailleurs menacés",
                    "quand": "non précisé",
                    "ou": "Bruxelles",
                    "extrait": "Nog eens 44 werknemers bedreigd met ontslag.",
                },
                {
                    "article": 2,
                    "chiffre": "60",
                    "mesure": "emplois",
                    "quand": "",
                    "ou": "",
                    "extrait": "Soixante emplois sont menacés.",
                },
                {"article": 9, "chiffre": "1", "mesure": "", "quand": "", "ou": "", "extrait": "x"},
            ],
            "conclusion": "  44 travailleurs  menacés. ",
        }
    )
    fact = read_fact(raw, articles, [])
    assert [(f.item_id, f.figure, f.figure_in_passage) for f in fact.lines] == [("a1", "44", True)]
    assert fact.dropped == 2
    assert fact.agreement is Agreement.UNE_SOURCE
    assert fact.conclusion == "44 travailleurs menacés."


def test_numbers_in_words_are_figures() -> None:
    """« quatre » at La DH, « vier » at Bruzz: the same four injured."""
    agreement, compared = concordance(
        [
            line("La DH", "quatre", "blessés", "vendredi", "Bruxelles"),
            line("Bruzz", "vier", "blessés", "vendredi", "Brussel"),
        ],
        BRUSSELS,
    )
    assert (agreement, [c.same for c in compared]) == (Agreement.CONCORDENT, [True])


def test_a_fact_reads_first_the_items_that_hold_the_question() -> None:
    texts = ["Tempête Austen : les dégâts", "L'alerte orange commence vendredi midi", "Austen"]
    assert reading_order("Quand l'alerte orange a-t-elle commencé ?", texts) == [1, 0, 2]
