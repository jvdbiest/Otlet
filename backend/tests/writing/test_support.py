# SPDX-License-Identifier: AGPL-3.0-or-later
"""The reading aid at the sentence (REL2): the source sentences that confirm or contradict."""

from otlet.writing.domain.support import SHOWN, supports

SOURCES = [
    "Grand Prix du Qatar : Marquez remporte la course sprint. Marc Márquez s'impose devant Fabio"
    " Di Giannantonio. Malgré une deuxième place qui lui a échappé dans le dernier tour face à"
    " Fabio Di Giannantonio, Martín termine sur le podium et empoche sept points.",
    "Le classement après le sprint. Ai Ogura complète le top 5 avec 281 unités. La météo sera"
    " clémente dimanche à Lusail, avec 28 degrés.",
]


def test_the_sentence_that_contradicts_an_error_is_shown_first() -> None:
    """The case of reference (RB1 §9): Martín second, when he lost second place."""
    found = supports(
        "Jorge Martín a terminé deuxième du sprint après avoir dépassé Fabio Di Giannantonio.",
        SOURCES,
    )
    assert found[0].source == 0
    assert found[0].sentence.startswith("Malgré une deuxième place qui lui a échappé")
    assert "Martín" in found[0].shared and "Giannantonio" in found[0].shared
    assert len(found) <= SHOWN


def test_a_figure_finds_its_source_and_nothing_shared_shows_nothing() -> None:
    found = supports("Johann Zarco complète le top 5 avec 281 points.", SOURCES)
    assert found[0].sentence == "Ai Ogura complète le top 5 avec 281 unités."
    assert found[0].source == 1 and "281" in found[0].shared
    assert supports("Une phrase sans rapport aucun.", SOURCES) == []
    assert supports("Martín", []) == []
