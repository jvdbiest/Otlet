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
    """A question as its folded words between spaces, its marks and quotes aside."""
    text = folded(question)
    for mark in '?,"«»“”':
        text = text.replace(mark, " ")
    return f" {' '.join(text.split())} "


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
    annonces disent parlant parler uniquement elements element trouves trouvees concernes
    concernees moins""".split()
)

# Places of the Veille (Belgian press): a place the question does not name is no term of its
# subject, and a place it names is a concept of its own (Joël, 2026-10-29: « perte d'emploi »
# came with « Bruxelles », and « budget » with « Région de Bruxelles-Capitale »).
# One line for each place, its names in the three languages: « Brussels-Capital Region » is
# the « Bruxelles-Capitale » of the question.
PLACE_NAMES = (
    "belgique belgie belgium belge belges belgische",
    "bruxelles brussel brussels bruxellois bruxelloise bruxelloises brusselse bruxelles-capitale"
    " brussel-hoofdstad brussels-capital",
    "wallonie wallonia wallonne wallon wallons wallonnes waals waalse",
    "flandre flandres vlaanderen flanders flamand flamande flamands vlaamse",
    "liege luik",
    "anvers antwerpen antwerp",
    "gand gent ghent",
    "charleroi",
    "namur namen",
    "mons bergen",
    "louvain leuven",
    "ostende oostende",
    "bruges brugge",
    "hainaut henegouwen",
    "limbourg limburg",
    "luxembourg luxemburg",
    "france frankrijk",
    "europe europa europeen europeenne europese",
)
PLACES = {word: line.split()[0] for line in PLACE_NAMES for word in line.split()}


def _named(question: str) -> list[str]:
    """The words of a question that name something: neither a question word, a period nor a
    language, nor a word shorter than five letters; folded."""
    asked = _asked(question)
    for words_of_period, _ in PERIOD_WORDS:
        asked = asked.replace(f" {words_of_period} ", " ")
    asked = MONTH_PERIOD.sub(" ", asked)
    language = {w for names in LANGUAGE_WORDS.values() for w in names}
    # Short names written in capitals name something too: « MR », « F1 », « GSK ».
    acronyms = {folded(w) for w in re.findall(r"[\w-]+", question) if len(w) >= 2 and w.isupper()}
    return [
        word
        for word in re.findall(r"[\w-]+", asked)
        if (len(word) >= 5 or word in acronyms)
        and word not in QUESTION_WORDS
        and word not in language
        and word not in MONTHS
    ]


def unsearched(question: str, concepts: list[Concept]) -> list[str]:
    """The words of the question that name something no term searches (« enseignement » when
    only « Belgique » was searched, Joël, 2026-10-29), in the author's spelling."""
    searched = {
        w for c in concepts for t in (c.name, *c.terms) for w in re.findall(r"[\w-]+", folded(t))
    }

    def stem(word: str) -> str:
        # « véhicule » is searched by « véhicules »: the plural aside first.
        word = word[:-1] if len(word) > 5 and word[-1] in "sx" else word
        return word[: max(5, len(word) - 2)]

    stems = {stem(w) for w in searched}
    originals = {folded(w): w for w in re.findall(r"[\w-]+", question)}
    out = []
    for word in _named(question):
        if word in searched or stem(word) in stems:
            continue
        shown = originals.get(word, word)
        if shown not in out:
            out.append(shown)
    return out


def _names(question: str, concept: Concept) -> bool:
    """The question names the concept: its name or one of its terms."""
    asked = _asked(question)
    words = set(asked.split())
    return any(
        len(w) > 1 and (f" {folded(w)} " in asked or folded(w) in words)
        for w in (concept.name, *concept.terms)
    )


def about_the_set(question: str, translated: Translated, state: State) -> bool:
    """A « search » that names nothing new is a question about the set:
    - every word of it the set already searches: « qui parle de budget », after the budget of
      Brussels, searched « acteurs, ministres, participants » without « budget »;
    - none of its concepts named by the question: « et quel est le véhicule électrique le
      moins cher ? » searched « modèle » alone (Joël, 2026-10-29)."""
    if translated.operation is not Operation.CHERCHER or not state.concepts:
        return False
    if unsearched(question, list(state.concepts)):
        return False  # « Et l'enseignement ? »: a new subject
    return bool(_named(question)) or not any(_names(question, c) for c in translated.concepts)


def _words(text: str) -> str:
    """A text as its folded words, hyphenated words kept whole, between spaces."""
    return " " + " ".join(re.findall(r"[\w-]+", folded(text))) + " "


def _likeness(term: str, part: str) -> int:
    """How close a term is to a part of a name: a shared word, else the longest shared start
    of two words (Brussel, Brussels-Capital Region and Bruxelles-Capitale share « bru »)."""
    best = 0
    for a in _words(term).split():
        for b in _words(part).split():
            if a == b:
                return 100
            n = 0
            while n < min(len(a), len(b)) and a[n] == b[n]:
                n += 1
            best = max(best, n)
    return best


def split_mixed(concept: Concept) -> tuple[Concept, ...]:
    """A concept that names two things, as one concept for each. « budget de la région
    Bruxelles-Capitale » with the terms « budget » and « Bruxelles-Capitale » searched budget OR
    Brussels: the budgets of Mons and Seneffe, a storm in Brussels (Joël, 2026-10-29). Its parts
    are the shortest terms its name holds; every other term goes to the part it is closest to,
    or is dropped when it is close to none."""
    name = _words(concept.name)
    inside = [t for t in concept.terms if _words(t).strip() and _words(t) != name]
    inside = [t for t in inside if _words(t) in name]
    parts = [t for t in inside if not any(o != t and _words(o) in _words(t) for o in inside)]
    if len(parts) < 2:
        return (concept,)
    groups: dict[str, list[str]] = {p: [p] for p in parts}
    for term in concept.terms:
        if term in parts or _words(term) == name:
            continue
        scores = sorted(((_likeness(term, p), p) for p in parts), reverse=True)
        if scores[0][0] >= 3 and scores[0][0] > scores[1][0]:
            groups[scores[0][1]].append(term)
    return tuple(Concept(p, _clean(groups[p])) for p in parts)


def _same_concept(a: Concept, b: Concept) -> bool:
    """The concept added is one the set holds, by its name, hyphens aside: « Bruxelles
    Capitale » restricts nothing more than « Bruxelles-Capitale ». Sharing a term is not
    enough: « Belgique » with « Bruxelles » among its terms was taken for the Brussels already
    in « perte d'emploi », and « uniquement en Belgique » restricted nothing (Joël, 2026-10-29)."""

    def key(text: str) -> str:
        return folded(text).replace("-", " ")

    return key(a.name) in {key(t) for t in (b.name, *b.terms)}


def _place_words(term: str) -> set[str]:
    """The places a text names, each by the first of its names."""
    words = set(_words(term).split())
    return {PLACES[w] for w in words | {p for w in words for p in w.split("-")} if w in PLACES}


def placed(question: str, concept: Concept) -> tuple[Concept, ...]:
    """A subject without the places the model added to it: a place the question names is a
    concept of its own, one it does not name is dropped. A concept that is a place stays."""
    if _place_words(concept.name) or not any(_place_words(t) for t in concept.terms):
        return (concept,)
    asked = _place_words(question)
    subject = [t for t in concept.terms if not _place_words(t)]
    places = [t for t in concept.terms if _place_words(t) & asked]
    out = [Concept(concept.name, _clean(subject))] if subject else []
    if places:
        # Led by the place as the question writes it, so that the question names it.
        found = set().union(*(_place_words(t) for t in places))
        written = [w for w in re.findall(r"[\w-]+", question) if _place_words(w) & found]
        name = written[0] if written else places[0]
        out.append(Concept(name, _clean([name, *places])))
    return tuple(out) or (concept,)


# Names that hold a term without meaning it (Joël, 2026-10-29: « Bruxelles-Capitale n'a rien à
# voir avec Wallonie-Bruxelles »). The engine finds « Bruxelles » in « Fédération
# Wallonie-Bruxelles »; an item that names Brussels only so is not about Brussels.
FALSE_FRIENDS = ("wallonie-bruxelles", "wallonie-brussel", "wallonia-brussels")


def only_false_friends(text: str, terms: tuple[str, ...]) -> bool:
    """True when the text names a false friend and no term of the concept as a whole word:
    « Fédération Wallonie-Bruxelles : le budget 2027 » for « Bruxelles ». A text that names
    neither stays: the engine found the term further in the article."""
    words = _words(text)
    if not any(f" {friend} " in words for friend in FALSE_FRIENDS):
        return False
    return not any(_words(term) in words for term in terms if _words(term).strip())


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


# Words between quotes in a question are searched as they are written, side by side (Joël,
# 2026-10-29: « les actualités concernant le jeu "GTA VI" »).
QUOTED = re.compile(r'"([^"]{2,80})"|«\s*([^»]{2,80}?)\s*»|“([^”]{2,80})”')
ROMAN = dict(
    zip(
        "i ii iii iv v vi vii viii ix x xi xii xiii xiv xv xvi xvii xviii xix xx".split(),
        range(1, 21),
        strict=True,
    )
)


def quoted(question: str) -> list[str]:
    """The phrases of a question between quotes, " ", « » or “ ”."""
    found = (" ".join(next(g for g in m.groups() if g).split()) for m in QUOTED.finditer(question))
    return list(dict.fromkeys(p for p in found if p))


def numbered(phrase: str) -> list[str]:
    """The phrase and its other numbering: « GTA VI » and « GTA 6 », « Windows 11 » and
    « Windows XI »; a single word is never renumbered."""
    words = phrase.split()
    if len(words) < 2:
        return [phrase]
    arabic = {str(n): r.upper() for r, n in ROMAN.items()}
    other = [str(ROMAN[w.lower()]) if w.lower() in ROMAN else arabic.get(w, w) for w in words]
    return list(dict.fromkeys([phrase, " ".join(other)]))


def with_quoted(question: str, concepts: tuple[Concept, ...]) -> tuple[Concept, ...]:
    """Every phrase of the question between quotes searched as a phrase, with its other
    numbering: in the concept that names it already, else in a concept of its own, first."""
    out = list(concepts)
    for phrase in quoted(question):
        terms = [f'"{p}"' for p in numbered(phrase)]
        keys = {folded(p).replace('"', "") for p in numbered(phrase)}
        at = next(
            (
                n
                for n, c in enumerate(out)
                if keys & {folded(t).replace('"', "") for t in (c.name, *c.terms)}
            ),
            None,
        )
        if at is None:
            out.insert(0, Concept(phrase[:TERM_MAX_LENGTH], _clean(terms)))
            continue
        concept = out[at]
        rest = [t for t in concept.terms if folded(t).replace('"', "") not in keys]
        out[at] = Concept(concept.name, _clean([*terms, *rest]))
    return tuple(out)


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

    proposed = tuple(
        placed_part
        for c in translated.concepts
        # A concept named by a word of the question that names nothing (« parlant »).
        if folded(c.name) not in QUESTION_WORDS
        for part in split_mixed(c)
        for placed_part in placed(question, part)
    )
    # The same concept twice (« GTA » and « GTA »): once.
    proposed = tuple({folded(c.name): c for c in reversed(proposed)}.values())[::-1]
    kept_concepts = tuple(c for c in map(anchored, proposed) if c is not None)
    dropped = [c for c in proposed if anchored(c) is None and not _of_period(c)]
    missing = unsearched(question, list(kept_concepts))
    if dropped and missing and kept_concepts:
        # The model named the subject otherwise (« éducation » for « enseignement »): its
        # concept comes back, led by the word of the question (Joël, 2026-10-29).
        word = missing[0]
        kept_concepts = (*kept_concepts, Concept(word, _clean([word, *dropped[0].terms])))
    period = asked_period(question, today)
    # None named: the first stays, unless it is made of the words of a period.
    fallback = tuple(c for c in proposed[:1] if not _of_period(c))
    kept = replace(
        translated, concepts=with_quoted(question, kept_concepts or fallback), days=period
    )
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
            # A place the set already holds restricts nothing more (« Seulement Bruxelles
            # Capitale » after the budget of the Région de Bruxelles-Capitale).
            added = [
                c for c in proposed[:1] if not any(_same_concept(c, s) for s in state.concepts)
            ]
            concepts = (*state.concepts, *added)[:CONCEPTS_MAX]
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
