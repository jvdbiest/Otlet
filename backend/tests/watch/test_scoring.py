# SPDX-License-Identifier: AGPL-3.0-or-later
"""The lexical score of an item for a topic, and its explanation (U02, F-VEI-02)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from otlet.watch.domain import model
from otlet.watch.domain.model import Candidate, Contribution, Rules, Topic, WatchError

SOURCE = uuid.uuid4()


def topic(
    keywords: list[str],
    exclusions: list[str] | None = None,
    languages: list[str] | None = None,
    source_ids: list[uuid.UUID] | None = None,
    whole_sources: bool = False,
) -> Rules:
    return Rules.of(
        Topic(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            name="Sujet",
            description="",
            keywords=tuple(keywords),
            exclusions=tuple(exclusions or ()),
            languages=tuple(languages or ()),
            source_ids=tuple(source_ids or ()),
            created_at=datetime.now(UTC),
            whole_sources=whole_sources,
        )
    )


def item(title: str, text: str = "", language: str | None = "fr") -> Candidate:
    return Candidate(title=title, text=text, language=language, source_id=SOURCE)


def test_the_score_is_the_sum_of_its_explanation() -> None:
    match = topic(["élection", "Parlement européen"]).match(
        item(
            "Élections au Parlement européen",
            "Les élections européennes. Une election. Encore une élection, et une élection.",
        )
    )
    assert match is not None
    assert match.contributions == (
        Contribution("élection", "title", 1, 3),
        Contribution("élection", "text", 3, 3),  # four occurrences, counted up to three
        Contribution("Parlement européen", "title", 1, 3),
    )
    assert match.score == 9 == sum(c.points for c in match.contributions)


def test_case_accents_plurals_and_prefixes() -> None:
    rules = topic(["climat*", "IA"])
    match = rules.match(item("Politiques CLIMATIQUES", "L'ia générative et les IAs."))
    assert match is not None
    assert {(c.term, c.where) for c in match.contributions} == {
        ("climat*", "title"),
        ("IA", "text"),
    }
    # A word is a whole word: "IA" is not found in "familiale".
    assert topic(["IA"]).match(item("Aide familiale")) is None


def test_a_phrase_must_appear_in_order() -> None:
    rules = topic(['"intelligence artificielle"'])
    assert rules.match(item("L'intelligence artificielle progresse")) is not None
    assert rules.match(item("Une intelligence, pas artificielle")) is None


def test_an_exclusion_removes_the_item() -> None:
    rules = topic(["football"], exclusions=["américain"])
    assert rules.match(item("Football : la finale")) is not None
    assert rules.match(item("Football", "le football américain")) is None


def test_languages_and_sources_limit_the_topic() -> None:
    assert topic(["AI"], languages=["en"]).match(item("AI news", language="en-GB")) is not None
    assert topic(["AI"], languages=["en"]).match(item("AI news", language="fr")) is None
    assert topic(["AI"], languages=["en"]).match(item("AI news", language=None)) is None
    assert topic(["AI"], source_ids=[uuid.uuid4()]).match(item("AI news")) is None
    assert topic(["AI"], source_ids=[SOURCE]).match(item("AI news")) is not None


def test_no_keyword_found_means_no_match() -> None:
    assert topic(["énergie"]).match(item("Rien à voir", "vraiment rien")) is None


def test_freshness_points() -> None:
    assert model.freshness_points(timedelta(hours=2)) == 2
    assert model.freshness_points(timedelta(hours=48)) == 1
    assert model.freshness_points(timedelta(days=5)) == 0


@pytest.mark.parametrize(
    ("keywords", "code"),
    [
        ([], "no_keywords"),
        ([" ", ""], "no_keywords"),
        (["***"], "invalid_terms"),
        (["x" * 101], "term_too_long"),
        ([f"terme {n}" for n in range(51)], "too_many_terms"),
    ],
)
def test_keywords_are_checked(keywords: list[str], code: str) -> None:
    with pytest.raises(WatchError) as caught:
        model.check_terms(keywords, required=True)
    assert caught.value.code == code


def test_terms_are_cleaned_and_deduplicated() -> None:
    assert model.check_terms(
        ["  IA ", "IA", "énergie   solaire", "Election*", "élection*"], required=True
    ) == (
        "IA",
        "énergie solaire",
        "Election*",
    )
    assert model.check_languages(["FR", "en", "fr"]) == ("fr", "en")
    with pytest.raises(WatchError):
        model.check_languages(["klingon"])


def test_every_item_of_the_sources_may_belong_to_the_topic() -> None:
    whole = topic([], source_ids=[SOURCE], whole_sources=True)
    match = whole.match(item("MOTOCROSS des Nations"))
    assert match is not None
    assert match.contributions == (Contribution("", "source", 1, model.SOURCE_POINTS),)
    # Keywords add their points; exclusions and languages still apply.
    rich = topic(
        ["moto*"], exclusions=["F1"], languages=["fr"], source_ids=[SOURCE], whole_sources=True
    )
    scored = rich.match(item("Essai moto", "La moto du mois."))
    assert scored is not None and scored.score == model.SOURCE_POINTS + 3 + 1
    assert rich.match(item("F1 : Sergio Pérez")) is None
    assert rich.match(item("Motocross", language="en")) is None
    # Another source is not taken, and without the option the keywords are still required.
    assert whole.match(Candidate("Moto", "", "fr", uuid.uuid4())) is None
    assert topic(["moto"], source_ids=[SOURCE]).match(item("Motocross")) is None


def test_every_item_of_the_sources_needs_a_source() -> None:
    with pytest.raises(WatchError) as caught:
        model.check_whole_sources(True, ())
    assert caught.value.code == "no_sources"
    assert model.check_whole_sources(True, (SOURCE,)) is True
