# SPDX-License-Identifier: AGPL-3.0-or-later
"""The language of a text that declares none, guessed from its frequent words."""

import pytest

from otlet.collection.domain.model import guess_language


@pytest.mark.parametrize(
    ("text", "language"),
    [
        (
            "Moins de faillites qu'en septembre, mais trois secteurs battent des records et les"
            " pertes d'emplois augmentent dans la région, selon les chiffres publiés pour le mois.",
            "fr",
        ),
        (
            "Trump calls the renewed strikes on Russian oil refineries a disgrace, and says that"
            " the talks are on hold for now. It was the third attack this week.",
            "en",
        ),
        (
            "Die Regierung hat am Montag einen neuen Plan für die Energie vorgestellt, der auch"
            " die Preise senken soll. Es ist nicht der erste Versuch.",
            "de",
        ),
        (
            "Het kabinet heeft een nieuw plan voor de energie gepresenteerd, dat ook de prijzen"
            " moet verlagen. Het is niet de eerste poging van de regering.",
            "nl",
        ),
        (
            "El gobierno presentó el lunes un nuevo plan para la energía, que también debe bajar"
            " los precios. No es el primer intento, pero sus críticos dudan.",
            "es",
        ),
        (
            "Il governo ha presentato lunedì un nuovo piano per l'energia, che deve anche ridurre"
            " i prezzi. Non è il primo tentativo della maggioranza, e gli esperti sono cauti.",
            "it",
        ),
        (
            "O governo apresentou na segunda-feira um novo plano para a energia, que também deve"
            " baixar os preços. Não é a primeira tentativa, e os críticos são cautelosos.",
            "pt",
        ),
    ],
)
def test_a_text_tells_its_language(text: str, language: str) -> None:
    assert guess_language(text) == language


def test_too_short_or_too_mixed_tells_nothing() -> None:
    assert guess_language("MOTOCROSS des Nations") is None
    assert guess_language("") is None
    mixed = "the and of to is that for le la les des un une est"
    assert guess_language(mixed) is None
