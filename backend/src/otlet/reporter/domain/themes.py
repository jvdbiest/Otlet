# SPDX-License-Identifier: AGPL-3.0-or-later
"""The main themes of a large set, from the words of its titles and summaries, without a model
(Joël, 2026-10-29): « J'ai trouvé 200 articles. Principaux sujets : enseignement supérieur
(52), réforme scolaire (41)… Que souhaitez-vous explorer ? ».

A theme is a word or a pair of words that many items of the set share, other than the terms
searched; each theme keeps its items, so that the author opens them in one click. Themes that
cover nearly the same items are one theme.
"""

import re
from dataclasses import dataclass

from otlet.assistant.domain.terms import folded

THEMES_MAX = 6
SHARED_MIN = 3
# Two themes whose items are mostly the same are one: the second is left out.
OVERLAP_MAX = 0.7
# The first letters that make one word of its forms.
STEM = 8
STOP = set(
    """
    alors apres aussi autre autres avant avec avoir bien cela celle celui ces cet cette chez
    comme comment dans depuis des deux doit donc dont elle elles encore entre est etait etre
    fait faire font leur leurs lors mais meme moins notre nous par pas peu peut plus pour quand
    que quel quelle quelles quels qui sans selon ses seulement son sont sous sur tous tout toute
    toutes tres une vers vous ans fois jour jours semaine mois annee hier aujourd'hui lundi mardi
    mercredi jeudi vendredi samedi dimanche janvier fevrier mars avril mai juin juillet aout
    septembre octobre novembre decembre selon voici voila actualite actualites article video
    nouveau nouvelle nouveaux nouvelles premier premiere dernier derniere grand grande petit
    petite bon bonne plus moins tres trop sera serait ont avait avaient plusieurs personnes
    personne gens cas partie place part point fin debut suite heure heures minutes pres
    contre deja ainsi enfin toujours jamais beaucoup
    aan als bij dan dat die dit door een het hij hoe maar met naar niet nog ook over tot uit van
    voor wat wel werd wordt zijn zich zou zal
    about after also and are been but for from has have into its more not over than that the
    their this was were what when which who will with
    """.split()
)


@dataclass(frozen=True, slots=True)
class Theme:
    label: str
    members: tuple[int, ...]  # positions in the set


def _words(text: str) -> list[tuple[str, str]]:
    """(folded, as written) for each word of a text."""
    # « L'enseignement » is « enseignement »: the apostrophe parts the words.
    return [(folded(w), w) for w in re.findall(r"\w[\w-]*", text)]


def themes(texts: list[str], searched: list[str], limit: int = THEMES_MAX) -> list[Theme]:
    """The themes of the set, the most shared first."""
    # The terms searched and their kin (« belge » for « Belgique »): every item has them.
    excluded = {w[:4] for term in searched for w, _ in _words(term)}

    def usable(word: str) -> bool:
        return (
            len(word) > 3 and word not in STOP and word[:4] not in excluded and not word.isdigit()
        )

    members: dict[str, set[int]] = {}
    spelling: dict[str, dict[str, int]] = {}
    for n, text in enumerate(texts):
        words = _words(text)
        seen: set[str] = set()
        for i, (word, written) in enumerate(words):
            keys = []
            if usable(word):
                # One theme for the forms of a word: « manifestants », « manifestation ».
                keys.append((word[:STEM], written))
            if i + 1 < len(words) and usable(word) and usable(words[i + 1][0]):
                keys.append((f"{word} {words[i + 1][0]}", f"{written} {words[i + 1][1]}"))
            for key, shown in keys:
                if key in seen:
                    continue
                seen.add(key)
                members.setdefault(key, set()).add(n)
                forms = spelling.setdefault(key, {})
                forms[shown] = forms.get(shown, 0) + 1

    def weight(key: str) -> float:
        # A pair of words says more than one word: « enseignement supérieur » before « réforme ».
        return len(members[key]) * (1.5 if " " in key else 1.0)

    chosen: list[tuple[str, set[int]]] = []
    for key in sorted(members, key=lambda k: (-weight(k), k)):
        items = members[key]
        if len(items) < SHARED_MIN:
            continue
        if any(
            len(items & other) / min(len(items), len(other)) > OVERLAP_MAX for _, other in chosen
        ):
            continue
        if any(f" {key} " in f" {other} " or f" {other} " in f" {key} " for other, _ in chosen):
            continue
        chosen.append((key, items))
        if len(chosen) == limit:
            break
    return [
        Theme(max(spelling[key], key=lambda form: spelling[key][form]), tuple(sorted(items)))
        for key, items in chosen
    ]
