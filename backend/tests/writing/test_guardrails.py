# SPDX-License-Identifier: AGPL-3.0-or-later
"""The guardrails of a draft, first batch of U05: what no source writes, what a source wrote
already. Cases taken from the drafts of the quality audit (2026-10-19)."""

from otlet.writing.domain.brief import Length
from otlet.writing.domain.draft import longest_for, matter_level
from otlet.writing.domain.guardrails import copying, unsupported

SOURCE = (
    "Disney+ : 10 films parfaits à voir en streaming pour Halloween 2026. "
    "La Colline a des yeux. Pour fêter leur anniversaire de mariage, Big Bob Carter et sa femme "
    "Ethel ont demandé à leur famille de partir avec eux en Californie. Mais une route désertique "
    "va conduire les Carter vers le pire des cauchemars. Alien : Romulus, sorti en 2024."
)


def test_a_name_or_a_date_no_source_writes_is_found() -> None:
    draft = [
        "La Colline a des yeux, adapté d'un roman de Stephen King, suit Big Bob Carter et Ethel.",
        "Alien : Romulus, sorti en 2024, reprend la saga lancée en 1979 avec 1 200 figurants.",
    ]
    found = unsupported(draft, [SOURCE])
    assert [(f.kind, f.text) for f in found] == [
        ("name", "Stephen King"),
        ("date", "1979"),
        ("number", "1 200"),
    ]
    assert found[0].paragraph.startswith("La Colline a des yeux, adapté")


def test_a_number_written_otherwise_is_no_finding() -> None:
    assert unsupported(["Une perte de 47 000 euros."], ["une diminution de 47.000 euros"], "") == []
    assert unsupported(["Une hausse de 2,5 %."], ["une hausse de 3,5 %"], "") != []


def test_what_the_sources_or_the_author_write_is_no_finding() -> None:
    draft = [
        "Les Carter partent en Californie en 2024 ; selon l'auteur, une sélection Disney+.",
        "Dans sa maison, Ethel attend. Cependant, la route est longue.",  # words opening sentences
    ]
    assert unsupported(draft, [SOURCE]) == []
    # The author's own words (title, angle, instructions of the brief) are no invention.
    assert (
        unsupported(["Un regard de Joël Vanderbiest sur Big Bob."], [SOURCE], "Joël Vanderbiest")
        == []
    )


def test_a_copied_passage_is_found_and_measured() -> None:
    copied = copying(
        [
            "Mais une route désertique va conduire les Carter vers le pire des cauchemars, dit-on.",
            "Un texte écrit autrement, qui ne reprend rien de la source mot pour mot ici.",
        ],
        [SOURCE],
    )
    assert copied.share > 0.3 and len(copied.passages) == 1
    paragraph, excerpt, words = copied.passages[0]
    assert paragraph.startswith("Mais une route") and excerpt.startswith("Mais une route")
    assert words >= 12
    assert (
        copying(["Rien de commun avec la source, des mots tout à fait différents."], [SOURCE]).share
        == 0
    )


def test_the_length_holds_to_the_matter_of_the_sources() -> None:
    # The audit: 1,200 words asked of a source of 760, then padded, or filled in.
    assert longest_for(760) is Length.MEDIUM
    assert longest_for(2038) is Length.LONG
    assert longest_for(40) is None  # a summary: too thin even for a short article


def test_the_matter_has_three_levels() -> None:
    # Complete texts of 300 to 350 words gave faithful drafts (Honda, DeepSeek); 40 words of a
    # summary gave inventions (Nvidia).
    assert matter_level(760, full_text=True) == "enough"
    assert matter_level(317, full_text=True) == "limited"
    assert matter_level(352, full_text=False) == "insufficient"
    assert matter_level(40, full_text=False) == "insufficient"
    assert matter_level(120, full_text=True) == "insufficient"


def test_a_place_counts_as_written_under_any_of_its_forms() -> None:
    """« En France » rewords « sur le territoire français » (Joël, 2026-10-24): no finding; a
    place no source writes in any form is still found."""
    sources = [
        "Des risques liés à leur utilisation sur le territoire français, selon BFM TV.",
        "Des centaines de milliers de Belges touchés par des fuites de données.",
        "Settlers attacked diplomats in the West Bank; UK-funded vehicles in Dunkirk.",
    ]
    draft = [
        "Des inquiétudes persistent en France. Les fuites inquiètent en Belgique.",
        "Des colons attaquent en Cisjordanie. Rien de tel en Allemagne.",
        "Des véhicules venus du Royaume Uni, et non des États-Unis.",
    ]
    names = [f.text for f in unsupported(draft, sources) if f.kind == "name"]
    assert names == ["Allemagne", "États-Unis"]
