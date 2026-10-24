# SPDX-License-Identifier: AGPL-3.0-or-later
"""The matter of a brief: five criteria and the hybrid rule (ADR-0041)."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from otlet.writing.domain.brief import Length, Mode
from otlet.writing.domain.matter import (
    Evaluation,
    Mark,
    MatterItem,
    Nature,
    evaluate,
    publisher,
)

TODAY = date(2026, 10, 24)


def item(
    source: str,
    *,
    words: int = 400,
    days: int = 1,
    full_text: bool = True,
    duplicate_of: UUID | None = None,
) -> MatterItem:
    dated = datetime(2026, 10, 24, 9, tzinfo=UTC) - timedelta(days=days)
    return MatterItem(uuid4(), duplicate_of, source, dated, words, full_text)


def judge(
    items: list[MatterItem],
    length: Length = Length.SHORT,
    mode: Mode = Mode.SYNTHESIS,
    nature: Nature = Nature.NEWS,
) -> Evaluation:
    return evaluate(items, length, mode, nature, TODAY)


def marks(evaluation: Evaluation) -> dict[str, Mark | None]:
    return {criterion.name: criterion.mark for criterion in evaluation.criteria}


def test_three_publishers_fresh_and_long_enough_is_enough() -> None:
    evaluation = judge([item("a"), item("b"), item("c")])
    assert (evaluation.level, evaluation.reason) == ("enough", None)
    assert marks(evaluation) == {
        "sources": Mark.OK,
        "publishers": Mark.OK,
        "words": Mark.OK,
        "freshness": Mark.OK,
        "corroboration": None,
    }


def test_one_publisher_is_insufficient_whatever_the_rest() -> None:
    # Rewriting the coverage of one publisher: the risk of copying ADR-0038 fights.
    evaluation = judge([item("a", words=3000) for _ in range(4)])
    assert (evaluation.level, evaluation.reason) == ("insufficient", "publishers")


def test_six_items_five_from_one_site_is_only_limited() -> None:
    # The weighted rule gave this 88/100 (ADR-0041 §3).
    evaluation = judge([item("a") for _ in range(5)] + [item("b")])
    assert (evaluation.level, evaluation.reason) == ("limited", "publishers")
    assert marks(evaluation)["sources"] is Mark.OK


def test_background_is_not_judged_on_freshness() -> None:
    # The strict rule rejected this dossier de fond.
    items = [item("a", days=90), item("b", days=120), item("c", days=200)]
    news = judge(items)
    background = judge(items, nature=Nature.BACKGROUND)
    assert (news.level, news.reason) == ("limited", "freshness")
    assert (background.level, background.reason) == ("enough", None)
    assert marks(background)["freshness"] is Mark.FAIL  # still shown, as information


def test_freshness_counts_the_newest_item_in_days() -> None:
    evaluation = judge([item("a", days=40), item("b", days=12), item("c", days=60)])
    freshness = evaluation.criteria[3]
    assert (freshness.value, freshness.mark) == (12, Mark.WARN)
    assert evaluation.reason == "freshness"


def test_corroboration_is_not_evaluated_and_informs_in_panorama() -> None:
    synthesis = judge([item("a"), item("b"), item("c")])
    panorama = judge([item("a"), item("b"), item("c")], mode=Mode.PANORAMA)
    assert synthesis.criteria[4].informative is False
    assert panorama.criteria[4].informative is True
    assert synthesis.level == panorama.level == "enough"


def test_a_duplicate_counts_once() -> None:
    first = item("a")
    evaluation = judge([first, item("b", duplicate_of=first.id), item("c")])
    sources = evaluation.criteria[0]
    assert sources.value == 2
    assert evaluation.criteria[1].value == 2  # the duplicate's publisher does not count
    assert evaluation.criteria[2].value == 800


def test_words_follow_the_rule_of_adr_0038_against_the_length_asked() -> None:
    three = [item("a", words=300), item("b", words=300), item("c", words=300)]
    assert marks(judge(three, Length.MEDIUM))["words"] is Mark.OK  # 600 ≤ 0.8 × 900
    long = judge(three, Length.LONG)
    assert (long.level, long.reason) == ("limited", "words")
    assert (long.criteria[2].mark, long.criteria[2].longest) == (Mark.WARN, Length.MEDIUM)


def test_too_few_words_is_insufficient() -> None:
    summaries = [item(name, words=40, full_text=False) for name in "abc"]
    evaluation = judge(summaries)
    assert (evaluation.level, evaluation.reason) == ("insufficient", "words")
    # Complete texts of 300 words: limited, not insufficient (ADR-0038).
    texts = judge([item(name, words=100) for name in "abc"])
    assert (texts.level, texts.reason) == ("limited", "words")


def test_sources_fewer_than_three_warn() -> None:
    evaluation = judge([item("a", words=800), item("b", words=800)])
    assert marks(evaluation)["sources"] is Mark.WARN
    assert marks(evaluation)["publishers"] is Mark.WARN
    assert evaluation.reason == "sources"


def test_no_item_is_insufficient() -> None:
    evaluation = judge([])
    assert (evaluation.level, evaluation.reason) == ("insufficient", "sources")


def test_the_publisher_of_an_item() -> None:
    source, item_id = uuid4(), uuid4()
    assert publisher(source, None, "https://a.example/x", item_id) == f"source:{source}"
    assert publisher(None, "  Le   Monde ", None, item_id) == "origin:le monde"
    assert publisher(None, None, "https://www.lesoir.be/a/b", item_id) == "site:lesoir.be"
    assert publisher(None, "", None, item_id) == f"item:{item_id}"
