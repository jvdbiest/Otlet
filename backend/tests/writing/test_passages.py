# SPDX-License-Identifier: AGPL-3.0-or-later
"""What a long source sends, and the rules after the generation (bench of 2026-10-30)."""

import json
from datetime import UTC, datetime

from otlet.writing.domain.brief import BriefFields
from otlet.writing.domain.draft import (
    SourceText,
    asks_order,
    check_answer,
    in_order,
    messages,
    prompt_sources,
    without_copied_passages,
)
from otlet.writing.domain.guardrails import copied_sequences, longest_copy
from otlet.writing.domain.passages import GAP, passages, vocabulary

FILLER = "Le texte continue ici avec des mots sans rapport, longuement, pour remplir la page. "
ON_SUBJECT = "Le piratage par une IA reste sans preuve, disent les chercheurs dans leur rapport."
OPENING = "Une ouverture assez longue pour compter comme un vrai paragraphe du texte, " * 2
SOURCE = "\n".join(["Connexion", OPENING, *[FILLER * 3] * 6, ON_SUBJECT, *[FILLER * 3] * 6])


def source(title: str, text: str, day: int | None = None) -> SourceText:
    published = None if day is None else datetime(2026, 10, day, tzinfo=UTC)
    return SourceText(title, None, "Journal", published, text)


def test_a_long_source_sends_its_opening_and_its_passages_on_the_subject() -> None:
    sent = passages(SOURCE, 600, vocabulary("le piratage IA", [SOURCE]))
    assert sent.startswith("Une ouverture") and ON_SUBJECT in sent and GAP in sent
    assert len(sent) <= 600 and "Connexion" not in sent


def test_a_text_without_paragraphs_to_choose_from_is_cut_at_its_start() -> None:
    assert passages("x" * 5000, 600, {}) == "x" * 600


def test_the_room_of_short_sources_goes_to_the_long_ones() -> None:
    sources = prompt_sources([source("A", "court"), source("B", SOURCE)], 3000, "le piratage IA")
    assert not sources[0].cut and sources[1].cut and ON_SUBJECT in sources[1].text
    assert len(sources[1].text) > 1500


def test_the_prompt_gives_the_date_of_a_source_and_says_an_extract_has_gaps() -> None:
    sources = prompt_sources([source("A", SOURCE, day=24)], 600)
    user = messages(BriefFields(title="T", item_ids=(), language="fr"), sources)[1][1]
    assert "[S1] A (Journal), date: 24 octobre 2026" in user
    assert "[…] where some are left out" in user


def answer(*paragraphs: str, headings: tuple[str, ...] = ("Une", "Deux")) -> str:
    return json.dumps(
        {
            "title": "Le titre",
            "lead": "Une introduction assez longue.",
            "sections": [
                {"heading": heading, "paragraphs": [{"text": text, "source_ids": ["S1"]}]}
                for heading, text in zip(headings, paragraphs, strict=True)
            ],
            "sources_used": ["S1"],
        },
        ensure_ascii=False,
    )


COPIED = " ".join(f"mot{n}" for n in range(30)) + "."


def test_a_long_copied_passage_is_sent_back_then_taken_out() -> None:
    grams = copied_sequences([COPIED])
    assert longest_copy(COPIED, grams) == 30
    raw = answer(f"Une phrase écrite par le modèle. {COPIED}", "Un autre paragraphe, écrit.")
    found = check_answer(raw, ["S1"], copied_from=grams)
    assert found[0].startswith("passages copied word for word from a source: sections[0]")
    clean, removed = without_copied_passages(raw, grams)
    assert removed == [COPIED]
    assert json.loads(clean)["sections"][0]["paragraphs"][0]["text"].startswith("Une phrase")
    # A short shared turn of phrase stays.
    short = answer("mot0 mot1 mot2 mot3 mot4 mot5 mot6 mot7 mot8.", "Un autre, écrit ici.")
    assert check_answer(short, ["S1"], copied_from=grams) == []


def test_a_chronological_order_asked_is_followed() -> None:
    assert asks_order(BriefFields(title="T", item_ids=(), instructions="En ordre chronologique"))
    assert not asks_order(BriefFields(title="T", item_ids=(), instructions="Une liste"))
    raw = answer(
        "Le paragraphe du trente.",
        "Le paragraphe du vingt-huit.",
        "Le paragraphe du premier.",
        headings=("30 octobre 2026 : Après", "28 octobre 2026 : Avant", "1er septembre : Avant"),
    )
    headings = [s["heading"] for s in json.loads(in_order(raw))["sections"]]
    assert headings == [
        "1er septembre : Avant",
        "28 octobre 2026 : Avant",
        "30 octobre 2026 : Après",
    ]
