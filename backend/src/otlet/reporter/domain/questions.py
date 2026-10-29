# SPDX-License-Identifier: AGPL-3.0-or-later
"""A question of the author as an operation on the current set (ADR-0044 §3, §4).

The model translates; rules without a model keep the translation to what the question says. On
the bench of A2 (qwen3:14b, 25 questions) the model understood the operation 24 times, but it
added concepts the question never named (« impact, effet, ville ») and took « en néerlandais »
for a concept: two guards brought the items found from a few to 88 % of the reference.
"""

import json
import re
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from typing import Any

from otlet.assistant.domain.terms import TERM_MAX_LENGTH, Concept, folded

PROMPT_VERSION = "reporter-1"
QUESTION_MAX_LENGTH = 500
# A subject has one or two concepts; each « restreindre » adds one (Austen, Bruxelles, blessés).
CONCEPTS_MAX = 4
TERMS_MAX = 20
LANGUAGES = ("fr", "nl", "en")


class Operation(StrEnum):
    CHERCHER = "chercher"
    RESTREINDRE = "restreindre"
    ELARGIR = "élargir"
    TRIER = "trier"
    FAIT = "fait"
    AGIR = "agir"


@dataclass(frozen=True, slots=True)
class State:
    """What the conversation holds after a turn: the concepts of the set and its language."""

    concepts: tuple[Concept, ...] = ()
    language: str | None = None
    # A period the author named (« ces derniers jours »), in days; None: the conversation's.
    days: int | None = None


@dataclass(frozen=True, slots=True)
class Translated:
    operation: Operation
    concepts: tuple[Concept, ...]
    language: str | None
    days: int | None = None


OPERATION_SYSTEM = (
    "Tu es le Reporter d'Otlet, un documentaliste qui aide un auteur à explorer sa veille de "
    "presse belge (français, néerlandais, anglais). Traduis la dernière question de l'auteur en "
    "une opération sur l'ensemble d'articles courant :\n"
    "- « chercher » : un nouveau sujet ; donne 1 ou 2 concepts, chacun avec ses termes ;\n"
    "- « restreindre » : garder ceux qui parlent aussi d'autre chose (un lieu, un aspect) ; donne "
    "le concept ajouté et ses termes ; ou une langue (fr, nl, en) ;\n"
    "- « élargir » : ajouter des termes à un concept existant ;\n"
    "- « trier » : garder ceux qui portent vraiment sur le sujet ;\n"
    "- « fait » : une question dont la réponse est un nombre ou une date ;\n"
    "- « agir » : garder le dossier, préparer un brief.\n"
    "Termes : 1 à 3 mots, les formes courtes des titres de presse d'abord (Bruxelles, bruxellois, "
    "Brussel), dans les trois langues, 8 au plus par concept, jamais de terme trop général "
    "(« météo », « course », « nouveau »). Un concept ne contient que des mots qui le désignent : "
    "jamais un lieu ou un aspect dans le concept du sujet. Un sujet simple (un nom, un événement) "
    "n'a qu'un concept ; restreindre ajoute exactement un concept."
)
OPERATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": [o.value for o in Operation]},
        "concepts": {
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
        "langue": {"type": ["string", "null"]},
    },
    "required": ["operation", "concepts"],
}

# Words of a question that ask for a language (ADR-0044 §4): a filter, never a concept.
LANGUAGE_WORDS = {
    "nl": ("neerlandais", "neerlandophone", "neerlandophones", "flamand", "flamands", "nl"),
    "fr": ("francais", "francophone", "francophones"),
    "en": ("anglais", "anglophone", "anglophones"),
}


# Words of a question that name a period (Joël, 2026-10-25: « les actualités de piratage de ces
# derniers jours » kept the 30 days of the conversation, and the brief dated events of
# September). A filter, as a language is; the longest period named wins nothing: the first.
PERIOD_WORDS = (
    ("aujourd'hui", 1),
    ("du jour", 1),
    ("ce jour", 1),
    ("hier", 2),
    ("ces derniers jours", 7),
    ("ces jours-ci", 7),
    ("cette semaine", 7),
    ("de la semaine", 7),
    ("la semaine derniere", 14),
    ("ce mois", 31),
    ("du mois", 31),
)


MONTHS = (
    "janvier",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "decembre",
)
# « depuis octobre », « en octobre », « d'octobre »: from the first of that month (Joël,
# 2026-10-29: « Quels jeux vidéos sont sortis depuis octobre ? » searched « octobre 2023 »).
MONTH_PERIOD = re.compile(
    r"\b(?:depuis|en|d'|du mois d'|au mois d')\s*(" + "|".join(MONTHS) + r")\b"
)


def _asked(question: str) -> str:
    return f" {folded(question).replace('?', ' ').replace(',', ' ')} "


def asked_period(question: str, today: date | None = None) -> int | None:
    """The days a question names, from its words: « cette semaine » 7, « depuis octobre » from
    the first of October (the last October not after today)."""
    asked = _asked(question)
    named = next((days for words, days in PERIOD_WORDS if f" {words} " in asked), None)
    if named is not None:
        return named
    month = MONTH_PERIOD.search(asked)
    if month is None:
        return None
    today = today or date.today()
    number = MONTHS.index(month.group(1)) + 1
    year = today.year if number <= today.month else today.year - 1
    return (today - date(year, number, 1)).days + 1


PERIOD_TERMS = {
    "jour",
    "jours",
    "aujourd'hui",
    "semaine",
    "semaines",
    "week",
    "weekend",
    "week-end",
    "mois",
    "hier",
    "dag",
    "vandaag",
    "deze week",
    "today",
    "month",
    "maand",
}


def _of_period(concept: Concept) -> bool:
    """A concept made only of the words of a period: « semaine, week », « octobre 2025 »."""
    return all(
        w in PERIOD_TERMS or w in MONTHS or w.isdigit()
        for t in (concept.name, *concept.terms)
        for w in re.findall(r"[\w'-]+", folded(t))
    )


# Words of a question that ask, but name no subject: never « not searched ».
QUESTION_WORDS = set(
    """quel quels quelle quelles sont derniers dernieres dernier derniere faits fait concernant
    actualite actualites article articles nouvelles nouveaute nouveautes parle parlent passe
    passes quoi comment pourquoi combien depuis entre avant apres pendant cette semaine
    trouve trouver informations information evenements evenement marque marques recentes
    recents recent recente savoir plus est-ce qu'est-ce c'est sujet sujets concerne concernent
    lesquels lesquelles seulement aussi encore toutes tous sortis sorti sortent annonce
    annonces disent""".split()
)


def unsearched(question: str, concepts: list[Concept]) -> list[str]:
    """The words of the question that name something no term searches (« enseignement » when
    only « Belgique » was searched, Joël, 2026-10-29), in the author's spelling."""
    asked = _asked(question)
    for words_of_period, _ in PERIOD_WORDS:
        asked = asked.replace(f" {words_of_period} ", " ")
    asked = MONTH_PERIOD.sub(" ", asked)
    searched = {
        w for c in concepts for t in (c.name, *c.terms) for w in re.findall(r"[\w-]+", folded(t))
    }
    language = {w for names in LANGUAGE_WORDS.values() for w in names}

    def stem(word: str) -> str:
        return word[: max(5, len(word) - 2)]

    stems = {stem(w) for w in searched}
    originals = {folded(w): w for w in re.findall(r"[\w-]+", question)}
    out = []
    for word in re.findall(r"[\w-]+", asked):
        if len(word) < 5 or word in QUESTION_WORDS or word in language or word in MONTHS:
            continue
        if word in searched or stem(word) in stems:
            continue
        shown = originals.get(word, word)
        if shown not in out:
            out.append(shown)
    return out


def operation_message(history: list[str], state: State, question: str) -> str:
    current = " ; ".join(f"{c.name}: {', '.join(c.terms)}" for c in state.concepts) or "(aucun)"
    return (
        "Conversation :\n"
        + "\n".join(f"Auteur : {q}" for q in history)
        + f"\nConcepts de l'ensemble courant : {current}"
        + f"\nLangue : {state.language or 'toutes'}\n\nDernière question : {question}"
    )


def check_operation(raw: str) -> list[str]:
    """The errors of an answer, in words a model can act on; empty when usable."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        return [f"not JSON: {error.msg}"]
    if not isinstance(data, dict) or data.get("operation") not in {o.value for o in Operation}:
        return ["operation: one of " + ", ".join(o.value for o in Operation) + " is required"]
    if not isinstance(data.get("concepts"), list):
        return ["concepts: a list is required"]
    return []


def _clean(terms: list[Any]) -> tuple[str, ...]:
    seen: dict[str, str] = {}
    for term in terms:
        if isinstance(term, str):
            text = " ".join(term.split())[:TERM_MAX_LENGTH]
            if text and folded(text) not in seen:
                seen[folded(text)] = text
    return tuple(seen.values())[:TERMS_MAX]


def read_operation(raw: str) -> Translated:
    data = json.loads(raw)
    concepts = []
    for entry in data["concepts"]:
        if isinstance(entry, dict) and isinstance(entry.get("terms"), list):
            terms = _clean(entry["terms"])
            if terms:
                name = " ".join(str(entry.get("name") or terms[0]).split())[:TERM_MAX_LENGTH]
                concepts.append(Concept(name or terms[0], terms))
    language = data.get("langue")
    return Translated(
        Operation(data["operation"]),
        tuple(concepts),
        language if language in LANGUAGES else None,
    )


def guarded(question: str, translated: Translated, today: date | None = None) -> Translated:
    """The translation kept to what the question says (ADR-0044 §4):

    - a concept is kept only when the question names it, by its name or one of its terms;
      when none is named, the first stays, so that a search always has something;
    - a language the question names is a filter, never a concept: « Et en néerlandais ? »
      restricts the set to Dutch, whatever the model answered;
    - so is a period: its words name no concept (« cette semaine » gave a concept « semaine,
      week », which found every week-end of the Veille);
    - a concept the question names by its name searches that name first: « jeux vidéo » came
      with « console, PC, mobile » and not « jeux vidéo » itself (Joël, 2026-10-25)."""
    asked = _asked(question)
    for words_of_period, _ in PERIOD_WORDS:
        asked = asked.replace(f" {words_of_period} ", " ")
    asked = MONTH_PERIOD.sub(" ", asked)
    words = set(asked.split())

    def said(w: str) -> bool:
        return len(w) > 2 and (f" {folded(w)} " in asked or folded(w) in words)

    def anchored(concept: Concept) -> Concept | None:
        if not any(said(w) for w in (concept.name, *concept.terms)):
            return None
        if said(concept.name) and folded(concept.name) not in {folded(t) for t in concept.terms}:
            return Concept(concept.name, _clean([concept.name, *concept.terms]))
        return concept

    kept_concepts = tuple(c for c in map(anchored, translated.concepts) if c is not None)
    dropped = [c for c in translated.concepts if anchored(c) is None and not _of_period(c)]
    missing = unsearched(question, list(kept_concepts))
    if dropped and missing and kept_concepts:
        # The model named the subject otherwise (« éducation » for « enseignement »): its
        # concept comes back, led by the word of the question (Joël, 2026-10-29).
        word = missing[0]
        kept_concepts = (*kept_concepts, Concept(word, _clean([word, *dropped[0].terms])))
    period = asked_period(question, today)
    # None named: the first stays, unless it is made of the words of a period.
    fallback = tuple(c for c in translated.concepts[:1] if not _of_period(c))
    kept = replace(translated, concepts=kept_concepts or fallback, days=period)
    for code, names in LANGUAGE_WORDS.items():
        if words & set(names):
            return Translated(Operation.RESTREINDRE, (), code, period)
    return kept


def next_state(state: State, translated: Translated) -> State:
    """The concepts and language after the operation; the set follows them, without a model."""
    proposed = translated.concepts
    match translated.operation:
        case Operation.CHERCHER if proposed:
            # A new subject: a new set, in every language, over the period it names.
            return State(proposed[:2], None, translated.days)
        case Operation.RESTREINDRE:
            concepts = (state.concepts + proposed[:1])[:CONCEPTS_MAX]
            return State(
                concepts, translated.language or state.language, translated.days or state.days
            )
        case Operation.ELARGIR if state.concepts and proposed:
            last = state.concepts[-1]
            widened = Concept(last.name, _clean([*last.terms, *proposed[0].terms]))
            return State((*state.concepts[:-1], widened), state.language, state.days)
        case _:
            return state


def changes_set(operation: Operation) -> bool:
    return operation in (Operation.CHERCHER, Operation.RESTREINDRE, Operation.ELARGIR)
