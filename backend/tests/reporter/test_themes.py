# SPDX-License-Identifier: AGPL-3.0-or-later
"""The main themes of a large set, without a model (Joël, 2026-10-29)."""

from otlet.reporter.domain.themes import themes

TEXTS = [
    "Enseignement supérieur : le minerval augmente en Belgique",
    "L'enseignement supérieur flamand manifeste",
    "Enseignement supérieur : les étudiants dans la rue",
    "Réforme scolaire : les manifestants à Liège",
    "Réforme scolaire, la ministre répond aux manifestants",
    "La réforme scolaire divise les syndicats belges",
    "Manifestation des étudiants à Bruxelles",
    "Tempête Austen en Belgique",
]


def test_the_themes_of_a_set_are_its_shared_words() -> None:
    found = themes(TEXTS, ["Belgique", "Bruxelles", "Liège"])
    labels = {t.label: t.members for t in found}
    assert labels["Enseignement supérieur"] == (0, 1, 2)
    assert labels["Réforme scolaire"] == (3, 4, 5)
    # The forms of a word are one theme; the terms searched and their kin (« belges ») none.
    assert any(label.lower().startswith("manifest") for label in labels)
    assert not any("belg" in label.lower() for label in labels)
