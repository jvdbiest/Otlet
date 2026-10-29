# SPDX-License-Identifier: AGPL-3.0-or-later
"""A set read before it is trusted: « Vérifier en lisant » (Joël, 2026-10-29)."""

import json

from otlet.assistant.domain.terms import Concept
from otlet.reporter.domain.reading import (
    Coverage,
    Read,
    check_reading,
    concluded,
    read_reading,
    reading_message,
)

ITEMS = [
    Read("a", "Trou de 30 millions au budget montois", "Mons.", "Sudinfo", "2026-10-20", None),
    Read("b", "Brusselse regering : belastingkorting", "Brussel.", "Bruzz", "2026-10-21", None),
]


def test_the_judgement_is_kept_to_the_items_given() -> None:
    raw = json.dumps(
        {
            "repondent": [
                {"article": 2, "raison": "  le gouvernement bruxellois  "},
                {"article": 2, "raison": "deux fois"},
                {"article": 7, "raison": "hors liste"},
            ],
            "couverture": "partiel",
            "manque": "Aucun article ne donne le budget régional.",
            "autres_concepts": [
                {"name": "Région", "terms": ["gouvernement bruxellois", "Brusselse regering", ""]}
            ],
        }
    )
    assert check_reading(raw) == []
    judged = read_reading(raw, ITEMS, 1)
    assert [(a.item_id, a.reason, a.round) for a in judged.answers] == [
        ("b", "le gouvernement bruxellois", 1)
    ]
    assert judged.coverage is Coverage.PARTIEL
    assert judged.others == (Concept("Région", ("gouvernement bruxellois", "Brusselse regering")),)
    assert check_reading('{"repondent": [], "couverture": "peut-être"}')
    assert check_reading("pas du json")


def test_the_better_round_concludes() -> None:
    def judged(coverage: str, missing: str) -> str:
        return json.dumps(
            {"repondent": [], "couverture": coverage, "manque": missing, "autres_concepts": []}
        )

    first = read_reading(judged("non", "rien"), ITEMS, 1)
    second = read_reading(judged("partiel", "le montant manque"), ITEMS, 2)
    assert concluded(first, None) == (Coverage.NON, "rien")
    assert concluded(first, second) == (Coverage.PARTIEL, "le montant manque")


def test_the_message_holds_the_conversation_and_the_items() -> None:
    message = reading_message(["Le budget de Bruxelles"], "qui en parle ?", ITEMS)
    assert "Auteur : Le budget de Bruxelles" in message
    assert "Question à vérifier : qui en parle ?" in message
    assert "[2] Bruzz, 2026-10-21 — Brusselse regering" in message
