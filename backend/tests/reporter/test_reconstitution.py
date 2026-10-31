# SPDX-License-Identifier: AGPL-3.0-or-later
"""The rules of « Reconstituer » (ADR-0044 §7, §8), without a model."""

import json
from datetime import UTC, datetime

from otlet.reporter.domain.facts import Article
from otlet.reporter.domain.reconstitution import (
    Confidence,
    Facet,
    RebuiltLine,
    chosen_evenly,
    confidence,
    dated_days,
    read_analysis,
    read_facets,
    read_lines,
    unsupported,
    wrong_days,
)

DAY = datetime(2026, 10, 23, 12, tzinfo=UTC)  # a Friday
TEXT = (
    "Tempête Austen. La tempête a touché Bruxelles vendredi. Quatre personnes ont été blessées "
    "selon les pompiers, et 112 interventions ont eu lieu."
)
ARTICLE = Article("a", "La DH", TEXT)
OTHER = Article("b", "Bruzz", "Storm Austen. Vier gewonden in Brussel, zegt de brandweer vandaag.")
DATES = {"a": DAY, "b": DAY}
ASKED = "Où est passée la tempête Austen ? Lieux : par où est-elle passée ?"


def row(
    information: str, passage: str, article: int = 1, when: str = "vendredi"
) -> dict[str, object]:
    return {
        "article": article,
        "information": information,
        "quand": when,
        "ou": "Bruxelles",
        "extrait": passage,
    }


def lines(*rows: dict[str, object]) -> tuple[list[RebuiltLine], list[RebuiltLine], int]:
    raw = json.dumps({"lignes": list(rows)})
    return read_lines(raw, 1, [ARTICLE, OTHER], DATES, ASKED, [], [])


def test_a_line_stands_on_a_passage_of_its_article() -> None:
    kept, flagged, dropped = lines(
        row("Quatre blessés selon les pompiers", "Quatre personnes ont été blessées selon"),
        row("Six blessés", "Six personnes ont été blessées"),
        row("Quatre blessés", "Quatre personnes ont été blessées", article=9),
    )
    assert [line.information for line in kept] == ["Quatre blessés selon les pompiers"]
    assert (flagged, dropped) == ([], 2)
    assert kept[0].dated == DAY.isoformat() and kept[0].publisher == "La DH"


def test_a_line_that_says_nothing_or_repeats_a_passage_is_left_out() -> None:
    passage = "La tempête a touché Bruxelles vendredi."
    kept, flagged, dropped = lines(
        row("Lieux de la tempête Austen", passage),
        row("La tempête n'est pas mentionnée", passage),
        row("Bruxelles touchée vendredi", passage),
        row("Touchée vendredi : Bruxelles", passage),
    )
    assert [line.information for line in kept] == ["Bruxelles touchée vendredi"]
    assert (flagged, dropped) == ([], 0)


def test_a_line_that_adds_a_name_a_figure_or_a_wrong_day_is_to_check() -> None:
    passage = "Quatre personnes ont été blessées selon les pompiers"
    kept, flagged, _ = lines(
        row("Blessés à Namur selon les pompiers", passage),
        row("27 personnes blessées", passage),
        row("Blessées selon les pompiers", passage, when="mercredi 23 octobre"),
    )
    assert kept == []
    assert [line.to_check[0] for line in flagged] == [
        "Namur",
        "27",
        "mercredi 23 octobre (un vendredi)",
    ]


def test_the_calendar() -> None:
    assert wrong_days("mercredi 23 octobre", 2026) == ["mercredi 23 octobre (un vendredi)"]
    assert wrong_days("vendredi 23 octobre", 2026) == []
    assert "24 octobre samedi" in dated_days(DAY, "samedi prochain")


def test_a_sentence_says_what_its_lines_do_not_hold() -> None:
    assert unsupported("La tempête a fait 27 blessés à Namur.", "La tempête a fait 4 blessés") == [
        "27",
        "Namur",
    ]
    line = RebuiltLine(1, "a", "La DH", DAY.isoformat(), "Quatre blessés", "", "", "Quatre")
    raw = json.dumps(
        {
            "reponse": [{"texte": "Bruxelles a été touchée.", "lignes": [1], "deduction": False}],
            "phrases": [
                {"texte": "La tempête a touché Bruxelles.", "lignes": [1], "deduction": False},
                {"texte": "Elle a touché Namur le 24 octobre.", "lignes": [1], "deduction": True},
                {"texte": "Sans appui.", "lignes": [], "deduction": False},
            ],
        }
    )
    answer, sentences = read_analysis(raw, (line,), [ARTICLE])
    assert [s.text for s in answer] == ["Bruxelles a été touchée."]
    assert sentences[0].unsupported == ()
    assert sentences[1].deduction and "Namur" in sentences[1].unsupported
    assert sentences[2].unsupported == ("aucune ligne citée",)


def test_the_confidence_is_computed() -> None:
    facets = (Facet("Début", "Quand ?"), Facet("Fin", "Quand ?"))

    def line(facet: int, publisher: str, information: str = "Sans chiffre") -> RebuiltLine:
        return RebuiltLine(facet, publisher, publisher, DAY.isoformat(), information, "", "", "x")

    two = (line(1, "A"), line(1, "B"), line(2, "A"), line(2, "B"))
    assert confidence("chronologie", facets, two, []) == (Confidence.FORTE, ())
    one = (line(1, "A"), line(1, "B"), line(2, "A"))
    level, reasons = confidence("chronologie", facets, one, [])
    assert level is Confidence.MOYENNE and "ne tient qu'à une source (A)" in reasons[0]
    empty = (line(1, "A"), line(1, "B"))
    assert confidence("synthèse", facets, empty, [])[0] is Confidence.FAIBLE
    # Figures diverge in a chronology; in a synthesis, they are two proposals.
    apart = (
        line(1, "A", "4 blessés"),
        line(1, "B", "6 blessés"),
        line(2, "A"),
        line(2, "B"),
    )
    assert confidence("chronologie", facets, apart, [])[0] is Confidence.FAIBLE
    assert confidence("synthèse", facets, apart, [])[0] is Confidence.FORTE


def test_the_form_and_the_articles_read() -> None:
    raw = json.dumps(
        {
            "forme": "synthèse",
            "volets": [{"nom": f"V{n}", "question": "?"} for n in range(7)] + ["pas un volet"],
        }
    )
    form, facets = read_facets(raw)
    assert form == "synthèse" and len(facets) == 5
    evenly = chosen_evenly(list(range(30)))
    assert evenly[:3] == [0, 2, 4] and len(evenly) == 15
    assert chosen_evenly([1, 2]) == [1, 2]


def test_a_story_updated_gives_one_line_and_line_numbers_are_no_part_of_a_sentence() -> None:
    update = Article("c", "La DH", TEXT + " Mise à jour : rien de neuf.")
    raw = json.dumps(
        {
            "lignes": [
                row("Quatre blessés selon les pompiers", "Quatre personnes ont été blessées"),
                row("Quatre blessés selon les pompiers", "Quatre personnes ont été", article=2),
            ]
        }
    )
    dates = {"a": DAY, "c": DAY}
    kept, _, _ = read_lines(raw, 1, [ARTICLE, update], dates, ASKED, [], [])
    assert len(kept) == 1
    line = RebuiltLine(1, "a", "La DH", DAY.isoformat(), "Quatre blessés", "", "", "Quatre")
    answer = {"texte": "La tempête a touché Bruxelles (L1, L1).", "lignes": [1], "deduction": False}
    raw = json.dumps({"reponse": [answer], "phrases": []})
    sentences, _ = read_analysis(raw, (line,), [ARTICLE])
    assert sentences[0].text == "La tempête a touché Bruxelles."
    assert sentences[0].unsupported == ()


def test_the_answer_says_it_once_without_numbers_of_lines() -> None:
    line = RebuiltLine(1, "a", "La DH", DAY.isoformat(), "Quatre blessés", "", "", "Quatre")
    whole = {"texte": "La tempête a blessé quatre personnes. Bruxelles est touchée.", "lignes": [1]}
    again = {"texte": "Quatre personnes ont été blessées.", "lignes": [1]}
    detail = {
        "texte": "Bruxelles est touchée, comme indiqué dans les lignes 1 et 1.",
        "lignes": [1],
    }
    raw = json.dumps({"reponse": [whole, again], "phrases": [detail]})
    answer, sentences = read_analysis(raw, (line,), [ARTICLE])
    assert [s.text for s in answer] == [whole["texte"]]
    assert sentences[0].text == "Bruxelles est touchée."
    assert sentences[0].unsupported == ()


def test_the_answer_speaks_of_articles() -> None:
    line = RebuiltLine(1, "a", "La DH", DAY.isoformat(), "Quatre blessés", "", "", "Quatre")
    one = {"texte": "Les lignes ne disent pas la fin.", "lignes": [1]}
    answer, _ = read_analysis(json.dumps({"reponse": [one], "phrases": []}), (line,), [ARTICLE])
    assert answer[0].text == "Les articles lus ne disent pas la fin."


def test_the_year_is_told_and_a_year_the_lines_do_not_hold_is_flagged() -> None:
    from otlet.reporter.domain.reconstitution import analysis_message, numbered_articles

    line = RebuiltLine(1, "a", "La DH", DAY.isoformat(), "Quatre blessés", "", "", "Quatre")
    message = analysis_message("Combien ?", (line,), DAY.date())
    assert "Nous sommes le 23/10/2026." in message and "article du 23/10/2026" in message
    assert "article du 23/10/2026" in numbered_articles([ARTICLE], {"a": DAY})
    old = Article("a", "La DH", TEXT + " Depuis 2023, rien de tel.")
    wrong = {"texte": "Les articles datent de 2023.", "lignes": [1]}
    right = {"texte": "Les articles datent de 2026.", "lignes": [1]}
    raw = json.dumps({"reponse": [wrong, right], "phrases": []})
    answer, _ = read_analysis(raw, (line,), [old])
    assert answer[0].unsupported == ("2023",) and answer[1].unsupported == ()
