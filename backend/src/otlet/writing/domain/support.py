# SPDX-License-Identifier: AGPL-3.0-or-later
"""The reading aid at the level of the sentence (REL2, docs/spikes/REL2.md): for a sentence of a
draft, the sentences of its sources that share the most with it, its names and figures first.
No model: the author sees the sentence that confirms or contradicts, and judges.

REL2: shown under a sentence with an error written in (a figure, a month, a rank, two names
swapped), the source sentence that supported it before stayed shown 60 times of 60, the rarity
of the words counted on the sources of the brief alone, as here."""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

SHOWN = 3  # source sentences shown under a sentence, at most
SENTENCE_MIN = 20  # characters: shorter, a heading or a caption, not a statement
NAME_WEIGHT = 3.0
FIGURE_WEIGHT = 3.0
SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")
WORD = re.compile(r"[\w'’-]+")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
NAME = re.compile(r"\b[A-ZÀ-ÖØ-Ý][\w'’-]{2,}")
STOP = frozenset(
    """le la les un une des du de d l au aux en et ou à a est sont été être avoir ont il elle
    ils elles on ce cette ces cet qui que quoi dont où pour par sur dans avec sans plus moins
    pas ne se sa son ses leur leurs lui y mais comme aussi selon après avant entre lors
    très""".split()
)


@dataclass(frozen=True, slots=True)
class Support:
    """A sentence of a source under the sentence checked, with what they share."""

    source: int  # its index among the sources given
    sentence: str
    score: float
    shared: tuple[str, ...]  # the names and figures of the sentence checked it holds


def _fold(text: str) -> str:
    bare = unicodedata.normalize("NFKD", text.casefold().replace("’", "'"))
    return "".join(c for c in bare if not unicodedata.combining(c))


def _tokens(text: str) -> set[str]:
    out = set()
    for word in WORD.findall(text):
        folded = _fold(word)
        if len(folded) > 2 and folded not in STOP:
            # A light stem: « deuxième » and « deuxièmes », « réforme » and « réformes ».
            out.add(folded if folded.isdigit() else folded[:6])
    return out | {n.replace(",", ".") for n in NUMBER.findall(text)}


def _names(text: str) -> dict[str, str]:
    """The names of a text, folded, each with its spelling there."""
    return {_fold(n): n for n in NAME.findall(text)}


def _figures(text: str) -> dict[str, str]:
    return {n.replace(",", "."): n for n in NUMBER.findall(text)}


def supports(sentence: str, sources: list[str]) -> list[Support]:
    """The source sentences that share the most with `sentence`: words weighed by their rarity
    in these sources, each shared name and figure three times more. Only those reaching half
    the best score, at most SHOWN; nothing shared, nothing shown."""
    split = [
        [s.strip() for s in SENTENCE.split(text) if len(s.strip()) >= SENTENCE_MIN]
        for text in sources
    ]
    frequency = Counter(t for text in sources for t in _tokens(text))
    rarity = {t: math.log((1 + len(sources)) / (1 + n)) + 1 for t, n in frequency.items()}
    wanted, names, figures = _tokens(sentence), _names(sentence), _figures(sentence)
    scored = []
    for index, sentences in enumerate(split):
        for candidate in sentences:
            have = _tokens(candidate)
            shared_names = [names[n] for n in names if n in _names(candidate)]
            shared_figures = [figures[f] for f in figures if f in have]
            score = sum(rarity.get(t, 1.0) for t in wanted & have)
            score += NAME_WEIGHT * len(shared_names) + FIGURE_WEIGHT * len(shared_figures)
            if score > 0:
                shared = tuple(dict.fromkeys([*shared_names, *shared_figures]))
                scored.append(Support(index, candidate, round(score, 1), shared))
    scored.sort(key=lambda s: -s.score)
    best = scored[0].score if scored else 0.0
    return [s for s in scored if s.score >= best / 2][:SHOWN]
