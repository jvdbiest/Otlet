# SPDX-License-Identifier: AGPL-3.0-or-later
"""A set read before it is trusted: « Vérifier en lisant » (Joël, 2026-10-29).

The engine finds the items that hold the terms; nobody read them before they were shown. On
« le budget de la région Bruxelles-Capitale » the set held the budgets of Mons and Seneffe and a
storm in Brussels, and no item on the budget of the Region. Read as a person reads: the model
reads the titles and summaries of the first items, says which truly answer and what is missing,
and, when the question is not covered, gives other terms for one more search, read the same way.
Two rounds at most, one call each: the model runs on the author's own computer.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from otlet.assistant.domain.terms import TERM_MAX_LENGTH, Concept

READ_MAX = 30
ROUNDS_MAX = 2
SUMMARY_CHARS = 300
REASON_CHARS = 200
MISSING_CHARS = 400
OTHER_CONCEPTS_MAX = 2
OTHER_TERMS_MAX = 8


class Coverage(StrEnum):
    OUI = "oui"
    PARTIEL = "partiel"
    NON = "non"


@dataclass(frozen=True, slots=True)
class Read:
    """An item as the model reads it: numbered from 1 in the message."""

    item_id: str
    title: str
    summary: str
    publisher: str
    dated: str
    url: str | None


@dataclass(frozen=True, slots=True)
class Answer:
    """An item the model says truly answers, with its reason, and the round that found it."""

    item_id: str
    title: str
    publisher: str
    dated: str
    url: str | None
    reason: str
    round: int


@dataclass(frozen=True, slots=True)
class Round:
    """One search read: its concepts (the set's for the first), the items read, in order."""

    concepts: tuple[Concept, ...]
    read: tuple[str, ...]
    found: int


@dataclass(frozen=True, slots=True)
class Reading:
    # Asked and not yet done: the worker reads the set of the turn.
    requested: bool = False
    rounds: tuple[Round, ...] = ()
    answers: tuple[Answer, ...] = ()
    coverage: Coverage | None = None
    # The model's sentence on what the items read do not say: shown as the model's.
    missing: str = ""
    errors: tuple[str, ...] = field(default=())


READING_SYSTEM = (
    "Tu es le Reporter d'Otlet, un documentaliste. L'auteur explore sa veille de presse belge "
    "(français, néerlandais, anglais). Lis les articles numérotés (titre et résumé) comme un "
    "documentaliste : un article répond seulement s'il traite vraiment ce que l'auteur demande, "
    "pas s'il en partage un mot (« le budget de Mons » ne répond pas à une question sur le budget "
    "de la Région bruxelloise ; la Fédération Wallonie-Bruxelles n'est pas la Région de "
    "Bruxelles-Capitale). Un article qui ne mentionne le sujet qu'en passant ne répond pas. "
    "Lis la question avec la conversation. Réponds :\n"
    "- « repondent » : les numéros des articles qui répondent, chacun avec une raison courte ;\n"
    "- « couverture » : « oui » seulement si ces articles répondent pleinement à la question, "
    "« partiel » s'ils n'y répondent qu'en partie ou par un ou deux exemples, « non » sinon ;\n"
    "- « manque » : une phrase franche sur ce que ces articles ne disent pas (vide si rien) ;\n"
    "- « autres_concepts » : si la couverture n'est pas « oui », 1 ou 2 concepts pour chercher "
    "autrement, chacun avec 3 à 8 termes de 1 à 3 mots, tels que la presse les écrit dans ses "
    "titres, dans les trois langues (« gouvernement bruxellois », « Brusselse regering ») ; "
    "sinon une liste vide.\n"
    "Juge seulement sur ce qui est écrit : n'invente ni article ni fait."
)
READING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "repondent": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"article": {"type": "integer"}, "raison": {"type": "string"}},
                "required": ["article", "raison"],
            },
        },
        "couverture": {"type": "string", "enum": [c.value for c in Coverage]},
        "manque": {"type": "string"},
        "autres_concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "terms": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "terms"],
            },
        },
    },
    "required": ["repondent", "couverture", "manque", "autres_concepts"],
}


def reading_message(history: list[str], question: str, items: list[Read]) -> str:
    context = "\n".join(f"Auteur : {q}" for q in history)
    numbered = "\n".join(
        f"[{n}] {r.publisher}, {r.dated[:10]} — {r.title} — {r.summary[:SUMMARY_CHARS]}"
        for n, r in enumerate(items, 1)
    )
    return (
        f"Conversation :\n{context}\n\nQuestion à vérifier : {question}\n\nArticles :\n{numbered}"
    )


def check_reading(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        return [f"not JSON: {error.msg}"]
    if not isinstance(data, dict) or not isinstance(data.get("repondent"), list):
        return ["repondent: a list is required"]
    if data.get("couverture") not in {c.value for c in Coverage}:
        return ["couverture: oui, partiel or non is required"]
    return []


@dataclass(frozen=True, slots=True)
class Judgement:
    answers: tuple[Answer, ...]
    coverage: Coverage
    missing: str
    others: tuple[Concept, ...]


def read_reading(raw: str, items: list[Read], round_number: int) -> Judgement:
    """The model's judgement, kept to the items it was given: a number outside the list, or
    given twice, is dropped."""
    data = json.loads(raw)
    answers: dict[int, Answer] = {}
    for row in data["repondent"]:
        n = row.get("article") if isinstance(row, dict) else None
        if not isinstance(n, int) or not 1 <= n <= len(items) or n in answers:
            continue
        item = items[n - 1]
        reason = " ".join(str(row.get("raison", "")).split())[:REASON_CHARS]
        answers[n] = Answer(
            item.item_id, item.title, item.publisher, item.dated, item.url, reason, round_number
        )
    others = []
    for entry in data.get("autres_concepts") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("terms"), list):
            continue
        terms = tuple(
            dict.fromkeys(
                " ".join(t.split())[:TERM_MAX_LENGTH]
                for t in entry["terms"]
                if isinstance(t, str) and t.strip()
            )
        )[:OTHER_TERMS_MAX]
        if terms:
            name = " ".join(str(entry.get("name") or terms[0]).split())[:TERM_MAX_LENGTH]
            others.append(Concept(name or terms[0], terms))
    return Judgement(
        tuple(answers[n] for n in sorted(answers)),
        Coverage(data["couverture"]),
        " ".join(str(data.get("manque", "")).split())[:MISSING_CHARS],
        tuple(others[:OTHER_CONCEPTS_MAX]),
    )


def concluded(first: Judgement, second: Judgement | None) -> tuple[Coverage, str]:
    """The coverage and what is missing after the rounds: the better of the two coverages, with
    the sentence of the round that gave it."""
    if second is None:
        return first.coverage, first.missing
    order = [Coverage.NON, Coverage.PARTIEL, Coverage.OUI]
    best = max((second, first), key=lambda j: order.index(j.coverage))
    return best.coverage, best.missing
