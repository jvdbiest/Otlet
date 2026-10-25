# SPDX-License-Identifier: AGPL-3.0-or-later
"""What the model is asked, and how its answers are read (ADR-0043 §5): the concepts of a
subject, then a verdict and a reason for each candidate. The model orders; it never takes an
item out of sight: an item it could not judge goes « à vérifier ».

Rules from the bench of A1b (spikes/a1b-veille, second pass): the publisher's country is given;
the angle tells « traite » from « proche » and never sets aside; no link the item does not
write; an item without a summary is not sent, it goes « à vérifier »; an unknown number is
ignored.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

PROMPT_VERSION = "veille-2"
BATCH = 25
SUMMARY_SENT = 300
REASON_MAX_LENGTH = 300


class Verdict(StrEnum):
    TRAITE = "traite"  # retenu
    PROCHE = "proche"  # à vérifier
    HORS_SUJET = "hors_sujet"  # écarté, replié, jamais caché


@dataclass(frozen=True, slots=True)
class Judged:
    verdict: Verdict
    reason: str
    by_model: bool  # False: set by a rule (no summary, no answer)


NO_SUMMARY = Judged(Verdict.PROCHE, "Pas de résumé : à juger sur l'élément.", by_model=False)
NOT_JUDGED = Judged(Verdict.PROCHE, "Le modèle ne l'a pas jugé : à vérifier.", by_model=False)

EXPAND_SYSTEM = (
    "Tu prépares une recherche par mots-clés dans une veille de presse belge, en français, "
    "néerlandais et anglais. Découpe le sujet en concepts indispensables (2 au plus ; 1 si le "
    "sujet est un nom propre ou un événement). Pour chaque concept, donne les termes qui le "
    "désignent dans les trois langues. Pour un lieu ou une institution, donne d'abord les "
    "formes courtes des titres de presse (Bruxelles, bruxellois, Brussel, Brusselse), puis "
    "seulement les noms officiels, plus rares. Règles : chaque terme a 1 à 3 mots ; un concept par "
    "terme, jamais deux ; pas d'année ni de date que le sujet ne donne pas ; rien d'inventé "
    "(un nom propre reste tel quel) ; pas de terme qui trouverait tout (« actualité », "
    "« Belgique » seul) ; 8 termes au plus par concept.\n"
    "Exemple, sujet « Les loyers à Bruxelles » : concepts [{name: loyer, terms: [loyer, loyers, "
    "huur, huurprijzen, rent]}, {name: Bruxelles, terms: [Bruxelles, bruxellois, Brussel, "
    "Brusselse, Brussels]}]."
)
EXPAND_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "minItems": 1,
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "terms": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                },
                "required": ["name", "terms"],
            },
        }
    },
    "required": ["concepts"],
}

QUALIFY_SYSTEM = (
    "Tu aides un auteur à constituer la matière d'un article à partir de sa veille de presse. "
    "Pour chaque élément (titre et début de résumé, dans sa langue d'origine), dis s'il traite "
    "le sujet : « traite » s'il porte sur le sujet ; « proche » s'il en parle en passant ou "
    "traite un sujet voisin ; « hors_sujet » sinon. La raison, en français, 25 mots au plus, dit "
    "ce que traite l'élément, d'après son titre et son résumé seulement : ne déduis ni pays, ni "
    "date, ni auteur qu'ils ne donnent pas. Réponds pour chaque numéro reçu, et seulement pour "
    "eux.\n"
    "L'angle départage « traite » et « proche », il n'écarte jamais : un élément qui porte sur le "
    "sujet sans dire l'angle est au moins « proche ». Le pays de l'éditeur est donné entre "
    "crochets : un éditeur belge parle en général de la Belgique. Ne relie jamais l'élément au "
    "sujet par un fait qu'il n'écrit pas (une date, un événement, un lieu, un produit) : si le "
    "lien n'est pas écrit, l'élément est au plus « proche », et la raison le dit."
)
QUALIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "verdict": {"type": "string", "enum": [v.value for v in Verdict]},
                    "raison": {"type": "string"},
                },
                "required": ["n", "verdict", "raison"],
            },
        }
    },
    "required": ["verdicts"],
}


@dataclass(frozen=True, slots=True)
class Line:
    """A candidate as the model reads it."""

    title: str
    summary: str
    language: str | None
    publisher: str | None
    country: str | None


def subject_message(subject: str, angle: str) -> str:
    return f"Sujet : {subject}\nAngle : {angle or '(aucun)'}"


def qualify_message(subject: str, angle: str, lines: list[Line]) -> str:
    rows = [
        f"{n}. [{line.language or '?'} · {line.publisher or 'éditeur inconnu'} · "
        f"{line.country or 'pays inconnu'}] {line.title} — {line.summary[:SUMMARY_SENT]}"
        for n, line in enumerate(lines, 1)
    ]
    return subject_message(subject, angle) + "\n\nÉléments :\n" + "\n".join(rows)


def check_expand(raw: str) -> list[str]:
    """The errors of an answer to EXPAND, in words a model can act on; empty when usable."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        return [f"not JSON: {error.msg}"]
    concepts = data.get("concepts") if isinstance(data, dict) else None
    if not isinstance(concepts, list) or not 1 <= len(concepts) <= 2:
        return ["concepts: 1 or 2 concepts are required"]
    for n, concept in enumerate(concepts):
        terms = concept.get("terms") if isinstance(concept, dict) else None
        if not isinstance(terms, list) or not any(isinstance(t, str) and t.strip() for t in terms):
            return [f"concepts[{n}].terms: one term at least is required"]
    return []


def read_expand(raw: str) -> list[tuple[str, list[str]]]:
    data = json.loads(raw)
    return [
        (str(c.get("name", "")), [str(t) for t in c["terms"] if isinstance(t, str)])
        for c in data["concepts"]
    ]


def check_qualify(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        return [f"not JSON: {error.msg}"]
    verdicts = data.get("verdicts") if isinstance(data, dict) else None
    if not isinstance(verdicts, list):
        return ["verdicts: a list is required"]
    return []


def read_qualify(raw: str, count: int) -> dict[int, Judged]:
    """The verdicts of a batch of `count` lines, by their number (1…count). An unknown number
    or verdict is ignored: the item then goes « à vérifier » (NOT_JUDGED)."""
    out: dict[int, Judged] = {}
    for entry in json.loads(raw)["verdicts"]:
        if not isinstance(entry, dict):
            continue
        n, verdict = entry.get("n"), entry.get("verdict")
        if isinstance(n, int) and 1 <= n <= count and verdict in {v.value for v in Verdict}:
            reason = " ".join(str(entry.get("raison", "")).split())[:REASON_MAX_LENGTH]
            out[n] = Judged(Verdict(verdict), reason, by_model=True)
    return out
