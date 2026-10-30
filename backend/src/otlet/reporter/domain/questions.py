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

PROMPT_VERSION = "reporter-3"
QUESTION_MAX_LENGTH = 500
# A subject has one or two concepts; each « restreindre » adds one (Austen, Bruxelles, blessés).
CONCEPTS_MAX = 4
TERMS_MAX = 20
# A place may name its towns too (« Belgique »): as many terms as the author may send back.
PLACE_TERMS_MAX = 40
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
    # The meaning of the question that opened the search (ADR-0045): the items closest to it
    # join the items its words find. The first `subject` concepts are that search's; the
    # others restrict it, and the items found by the meaning must hold them too.
    meaning: tuple[float, ...] = ()
    subject: int = 0


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
    "Termes : pour chaque concept, trois listes, « fr », « nl » et « en », chacune de 1 à 4 "
    "termes de 1 à 3 mots, tels que la presse de cette langue les écrit dans ses titres "
    "(fr : hôpitaux, budget ; nl : ziekenhuizen, begroting ; en : hospitals, budget) ; un nom "
    "propre se répète tel quel dans chaque langue (Tesla), jamais de terme trop général "
    "(« météo », « course », « nouveau »). Un concept ne contient que des mots qui le désignent : "
    "jamais un lieu ou un aspect dans le concept du sujet. Un sujet simple (un nom, un événement) "
    "n'a qu'un concept ; restreindre ajoute exactement un concept. Un groupe (« les clubs "
    "belges », « les partis flamands ») se cherche par les noms de ses membres tels que la presse "
    "les écrit (Anderlecht, Union, Club Brugge, Genk…), pas par le nom du groupe."
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
                    "fr": {"type": "array", "items": {"type": "string"}},
                    "nl": {"type": "array", "items": {"type": "string"}},
                    "en": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "fr", "nl", "en"],
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
    ("vandaag", 1),
    ("today", 1),
    ("hier", 2),
    ("gisteren", 2),
    ("yesterday", 2),
    ("ces derniers jours", 7),
    ("ces jours-ci", 7),
    ("cette semaine", 7),
    ("de la semaine", 7),
    ("deze week", 7),
    ("this week", 7),
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
    text = folded(question).replace("’", "'")
    for mark in '?,"«»“”':
        text = text.replace(mark, " ")
    # « Les articles d'aujourd'hui » names a period too (Joël, 2026-10-30).
    text = text.replace("d'aujourd'hui", "aujourd'hui").replace("d'hier", "hier")
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


# The months in the other languages of the Veille: « October », « oktober » came as terms of
# « jeux vidéo » and found every item of October (bench, 2026-10-29).
OTHER_MONTHS = set(
    """january february march april may june july august september october november december
    januari februari maart mei juni juli augustus oktober""".split()
)


def _dated(term: str) -> bool:
    """A term made only of the words of a period or a date: « October », « oktober 2026 »."""
    words = re.findall(r"[\w'-]+", folded(term))
    return bool(words) and all(
        w in PERIOD_TERMS or w in MONTHS or w in OTHER_MONTHS or w.isdigit() for w in words
    )


# Heads that ask how something is seen, not what it is: « opinion des indépendants »
# searched the phrase and found nothing (bench, 2026-10-30).
VIEW_HEAD = re.compile(
    r"^(opinions?|avis|r[eé]actions?|positions?|point de vue|mening|reacties?|standpunt|"
    r"views?|reactions?)\s+(des|de la|de l'|du|de|d'|van de|van|of the|of)\s*",
    re.IGNORECASE,
)


def _seen(concept: Concept) -> Concept:
    """A concept without « opinion des », « réaction de »: the people, not the view."""
    name = VIEW_HEAD.sub("", concept.name).strip() or concept.name
    terms = tuple(VIEW_HEAD.sub("", t).strip() or t for t in concept.terms)
    return Concept(name, _clean([*terms])) if terms else concept


def _without_dates(concept: Concept) -> Concept:
    """A concept without its terms of a period: a period is a filter, never a term."""
    terms = tuple(t for t in concept.terms if not _dated(t))
    return Concept(concept.name, terms) if terms else concept


def _of_period(concept: Concept) -> bool:
    """A concept whose terms are only the words of a period: « semaine, week », « octobre
    2025 », or a concept « date » of « aujourd'hui, vandaag, today »."""
    return all(
        w in PERIOD_TERMS or w in MONTHS or w.isdigit()
        for t in concept.terms or (concept.name,)
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
    concernees moins avait avaient etait etaient aurait auraient sera seront aura auront
    peut peuvent doit doivent""".split()
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
    "flandre vlaanderen flandres flanders flamand flamande flamands vlaamse",
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
    "wavre waver",
    "ottignies louvain-la-neuve",
    "nivelles nijvel",
    "hasselt",
    "malines mechelen",
    "courtrai kortrijk",
    "tournai doornik",
    "arlon aarlen",
    "verviers",
    "seraing",
    "louviere louvière",
    "bastogne",
    "zaventem",
    "france frankrijk",
    "europe europa europeen europeenne europese",
)
PLACES = {word: line.split()[0] for line in PLACE_NAMES for word in line.split()}
# A country holds its regions and towns: « uniquement en Belgique » lost GSK, whose job
# losses were « à Wavre » (bench, 2026-10-29).
COUNTRY_PARTS = {
    "belgique": {
        line.split()[0] for line in PLACE_NAMES if line.split()[0] not in ("france", "europe")
    },
}


PRONOUN_SUFFIX = re.compile(r"(-t)?-(il|elle|ils|elles|on)$")


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
    out = []
    for word in re.findall(r"[\w-]+", asked):
        # « passe-t-il », « Quels-sont »: the parts of a word joined to a pronoun.
        word = PRONOUN_SUFFIX.sub("", word)
        if all(part in QUESTION_WORDS or len(part) < 5 for part in word.split("-")):
            if word not in acronyms:
                continue
        if word not in language and word not in MONTHS:
            out.append(word)
    return out


def proper_names(question: str) -> list[str]:
    """The names of the question: runs of words written with a capital, not the first word of
    the question, or a word in capitals (« Ahold Delhaize », « Novaïa Gazeta », « CPAS »)."""
    words = re.findall(r"[\w'-]+", question)
    runs: list[list[str]] = []
    for n, word in enumerate(words):
        bare = word.split("'")[-1]
        capital = bare[:1].isupper() and (n > 0 or (len(bare) > 1 and bare.isupper()))
        if capital and folded(bare) not in QUESTION_WORDS:
            if runs and runs[-1][-1] is words[n - 1]:
                runs[-1].append(word)
            else:
                runs.append([word])
    names = [" ".join(w.split("'")[-1] if i == 0 else w for i, w in enumerate(run)) for run in runs]
    return [n for n in names if _place_words(n) != {folded(n)} and len(n) > 1]


def unsearched(question: str, concepts: list[Concept]) -> list[str]:
    """The words of the question that name something no term searches (« enseignement » when
    only « Belgique » was searched, Joël, 2026-10-29), in the author's spelling."""
    searched = {
        # The terms only: a word left in the name is not searched (« grèves SNCB »).
        w
        for c in concepts
        for t in c.terms
        for w in re.findall(r"[\w-]+", folded(t))
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


def _said(term: str, asked: str) -> bool:
    """The question (as _asked) writes the term, in the singular or the plural: « grève » in
    « les grèves à la SNCB » (bench, 2026-10-29)."""
    term = folded(term)
    # « l'intelligence artificielle » writes « intelligence artificielle ».
    asked = f"{asked} {asked.replace(chr(39), ' ')} "
    words = set(asked.split())
    plurals = {term + "s", term + "x", term[:-1] if term[-1:] in "sx" else term}
    return len(term) > 1 and (f" {term} " in asked or term in words or bool(plurals & words))


def _names(question: str, concept: Concept) -> bool:
    """The question names the concept: its name or one of its terms."""
    asked = _asked(question)
    return any(_said(w, asked) for w in (concept.name, *concept.terms))


# Words of a question that point back to the set: « Qu'en pensent les enseignants ? » after
# « l'intelligence artificielle à l'école » searched teachers alone (bench, 2026-10-29).
ANAPHORA = (
    " qu'en ",
    " parmi ",
    " parmis ",
    " lesquels ",
    " lesquelles ",
    " ceux ",
    " celles ",
    " s'y ",
    " ce sujet ",
    " cela ",
    " ces articles ",
)


# A follow-up that asks who, how many, why… or is a fragment (« Sur les écouteurs ? ») asks
# within the set: « Qui sont les victimes ? » after the train crash in Spain searched victims
# of everything, « Sur les écouteurs ? » after the Black Friday every earphone (bench,
# 2026-10-30). « Et … ? » may open a new subject (« Et AWS ? »): it is not one of them.
WITHIN = (
    "qui",
    "que",
    "quoi",
    "quel",
    "quels",
    "quelle",
    "quelles",
    "combien",
    "pourquoi",
    "comment",
    "ou",
    "quand",
    "sur",
    "pour",
    "chez",
    "dans",
    "avec",
    "parmi",
)


def points_back(question: str) -> bool:
    asked = _asked(question)
    first = asked.split()[0] if asked.split() else ""
    first = first.split("-")[0].split("'")[0]
    return any(word in asked for word in ANAPHORA) or first in WITHIN


def about_the_set(question: str, translated: Translated, state: State) -> bool:
    """A « search » that names nothing new is a question about the set:
    - every word of it the set already searches: « qui parle de budget », after the budget of
      Brussels, searched « acteurs, ministres, participants » without « budget »;
    - none of its concepts named by the question: « et quel est le véhicule électrique le
      moins cher ? » searched « modèle » alone (Joël, 2026-10-29)."""
    if translated.operation is not Operation.CHERCHER or not state.concepts:
        return False
    # The words of the question must name the concepts themselves, not one of their terms:
    # « Et la Switch 2 ? » narrows « consoles » to one of its terms (bench, 2026-10-29).
    if unsearched(question, [Concept(c.name, (c.name,)) for c in state.concepts]):
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
    words = concept.name.split()
    if 2 <= len(words) <= 3 and all(w[:1].isupper() for w in words):
        return (concept,)  # « Edouard Philippe » is one person
    name = _words(concept.name)
    inside = [t for t in concept.terms if _words(t).strip() and _words(t) != name]
    inside = [t for t in inside if _words(t) in name]
    parts = [t for t in inside if not any(o != t and _words(o) in _words(t) for o in inside)]
    # An acronym of the name is a thing of its own even when no term is it alone: « grèves à
    # la SNCB » searched strikes OR the SNCB, and found the Dacia Striker (bench, 2026-10-30).
    covered = {w for p in parts for w in _words(p).split()}
    acronyms = [
        w
        for w in re.findall(r"[\w-]+", concept.name)
        if len(w) >= 2 and w.isupper() and folded(w) not in ROMAN and folded(w) not in covered
    ]
    parts += acronyms
    if len(parts) < 2:
        return (concept,)
    subject = next((p for p in parts if p not in acronyms), parts[0])
    groups: dict[str, list[str]] = {p: [p] for p in parts}
    for term in concept.terms:
        if term in parts or _words(term) == name:
            continue
        scores = sorted(((_likeness(term, p), p) for p in parts), reverse=True)
        if scores[0][0] >= 3 and scores[0][0] > scores[1][0]:
            groups[scores[0][1]].append(term)
        elif acronyms and not any(_words(a) in _words(term) for a in acronyms):
            # « stakingen » is like no part: it names the subject, not the acronym.
            groups[subject].append(term)
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


def _place_names(places: set[str]) -> list[str]:
    """Every name of the places, in the three languages, as the press writes them: « Brussel »
    and « Bruxelles » for « Bruxelles-Capitale » (bench, 2026-10-30: Bruzz wrote « Brussel »
    and « begroting », and the Reporter searched « Brussels-Capital »)."""
    lines = [line.split() for line in PLACE_NAMES]
    names = [w for line in lines if line[0] in places for w in line]
    parts = {p for place in places for p in COUNTRY_PARTS.get(place, ())} - places
    # The parts of a country after its own names: the first name of each, then the second.
    for rank in (0, 1):
        names += [line[rank] for line in lines if line[0] in parts and len(line) > rank]
    return list(dict.fromkeys(names))


# The little words a place leaves in a term: « hôpitaux en Flandre », « Région de
# Bruxelles-Capitale ».
PLACE_LINKS = set(
    """en de du des la le l in van of het the region regio regional gewest province provincie
    ville stad city commune gemeente""".split()
)


def _place_terms(places: set[str], own: list[str]) -> tuple[str, ...]:
    """The terms of a place concept: its common names first, in the spelling of the question
    or the model when they wrote them (« Bruxelles », « België »), then their own terms."""
    spelled = {folded(t): t for t in own}
    return _clean([*(spelled.get(n, n) for n in _place_names(places)), *own], PLACE_TERMS_MAX)


def _without_place(term: str) -> str:
    """A term without its place words and the little words they leave: « hôpitaux en
    Flandre » is « hôpitaux », « Vlaamse ziekenhuizen » is « ziekenhuizen »."""
    words = [w for w in term.split() if not _place_words(w) and folded(w) not in PLACE_LINKS]
    return " ".join(words)


def placed(question: str, concept: Concept) -> tuple[Concept, ...]:
    """A subject without the places in it: a place the question names is a concept of its own,
    with every name of that place; one it does not name is dropped. A concept that is only a
    place stays, with every name of that place."""
    asked = _place_words(question)
    if not _place_words(concept.name) and not any(_place_words(t) for t in concept.terms):
        return (concept,)
    subject_name = _without_place(concept.name)
    if not subject_name:
        # A place alone (« Flandre », « Bruxelles-Capitale »).
        alone = _place_words(concept.name) & asked or _place_words(concept.name)
        # The common names first: the first term is the measure of the others, and
        # « Brussel » (223 items) was set aside as too general next to « Bruxelles-Capitale »
        # (14) (bench, 2026-10-30).
        return (Concept(concept.name, _place_terms(alone, [concept.name, *concept.terms])),)
    subject = [s for s in (_without_place(t) for t in concept.terms) if s]
    out = [Concept(subject_name, _clean([subject_name, *subject]))]
    places = set().union(*(_place_words(t) for t in (concept.name, *concept.terms))) & asked
    if places:
        # Led by the place as the question writes it, so that the question names it.
        written = [w for w in re.findall(r"[\w-]+", question) if _place_words(w) & places]
        name = written[0]
        named = [t for t in concept.terms if _place_words(t) & places and not _without_place(t)]
        out.append(Concept(name, _place_terms(places, [name, *named])))
    return tuple(out)


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
    # Every language of the Veille, or its items are never found: the model gave « hôpitaux »
    # and the Flemish hospitals wrote « ziekenhuizen » (bench, 2026-10-30).
    return [
        f"concepts[{n}]: give terms in {lang} (a proper name is repeated as it is)"
        for n, entry in enumerate(data["concepts"])
        if isinstance(entry, dict)
        for lang in LANGUAGES
        if not _strings(entry.get(lang))
    ]


def _strings(value: Any) -> list[str]:
    return [v for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def _clean(terms: list[Any], most: int = TERMS_MAX) -> tuple[str, ...]:
    seen: dict[str, str] = {}
    for term in terms:
        if isinstance(term, str):
            text = " ".join(term.split())[:TERM_MAX_LENGTH]
            if text and folded(text) not in seen:
                seen[folded(text)] = text
    return tuple(seen.values())[:most]


def read_operation(raw: str) -> Translated:
    data = json.loads(raw)
    concepts = []
    for entry in data["concepts"]:
        if not isinstance(entry, dict):
            continue
        # Terms by language (reporter-3), or one list (before).
        written = [t for lang in LANGUAGES for t in _strings(entry.get(lang))]
        written += _strings(entry.get("terms"))
        if written:
            terms = _clean(written)
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


def _numbered_phrase(term: str) -> str:
    """A name with a number is a phrase: « Switch 2 » found « 2 » anywhere in a review of a
    Tamron lens with « switch » (bench, 2026-10-29)."""
    words = term.split()
    if term.startswith('"') or len(words) < 2:
        return term
    if any(w.isdigit() or folded(w) in ROMAN for w in words):
        return f'"{term}"'
    return term


def guarded(
    question: str, translated: Translated, today: date | None = None, every_word: bool = True
) -> Translated:
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
        return len(w) > 2 and _said(w, asked)

    def anchored(concept: Concept) -> Concept | None:
        if not any(said(w) for w in (concept.name, *concept.terms)):
            return None
        if said(concept.name) and folded(concept.name) not in {folded(t) for t in concept.terms}:
            return Concept(concept.name, _clean([concept.name, *concept.terms], PLACE_TERMS_MAX))
        return concept

    if translated.operation is Operation.FAIT and _asked(question).split()[:1] in (
        ["pourquoi"],
        ["comment"],
    ):
        # A fact is a number or a date; « Pourquoi … ? » asks for the articles that say why.
        translated = replace(translated, operation=Operation.CHERCHER)
    proposed = tuple(
        _without_dates(placed_part)
        for c in map(_seen, translated.concepts)
        for part in split_mixed(c)
        for placed_part in placed(question, part)
        # A concept named by a word of the question that names nothing (« parlant »), also
        # once split (« nouveautés » of « nouveautés Apple »).
        if folded(placed_part.name) not in QUESTION_WORDS
    )
    # The same concept twice (« GTA » and « GTA »): once.
    proposed = tuple({folded(c.name): c for c in reversed(proposed)}.values())[::-1]
    kept_concepts = tuple(c for c in map(anchored, proposed) if c is not None)
    dropped = [c for c in proposed if anchored(c) is None and not _of_period(c)]
    missing = unsearched(question, list(kept_concepts))
    # A name of the question no term searches is searched, whatever the operation: a name is
    # never what a fact counts (« Pourquoi Novaïa Gazeta ferme-t-elle ? » searched « fermeture »
    # alone, « Que rachète Ahold Delhaize ? » « rachat » alone, bench of 2026-10-30).
    # A number left out (« VI » of « GTA VI ») is no name; a name between quotes is searched
    # as written (with_quoted).
    left_out = {folded(w) for w in missing if folded(w) not in ROMAN and not w.isdigit()}
    quoted_words = {folded(w) for q in quoted(question) for w in q.split()}
    names = [
        n
        for n in proper_names(question)
        if {folded(w) for w in n.split()} & left_out
        and not {folded(w) for w in n.split()} <= quoted_words
    ]
    if names and translated.operation is not Operation.RESTREINDRE or (names and not kept_concepts):
        # Added to the model's subject, or to its first concept when the question named none.
        subject = kept_concepts or tuple(c for c in proposed[:1] if not _of_period(c))
        kept_concepts = (*subject, *(Concept(n, (n,)) for n in names[:2]))[:3]
        missing = unsearched(question, list(kept_concepts))
    if dropped and missing and kept_concepts and not names:
        # The model named the subject otherwise (« éducation » for « enseignement »): its
        # concept comes back, led by the word of the question (Joël, 2026-10-29).
        word = missing[0]
        kept_concepts = (*kept_concepts, Concept(word, _clean([word, *dropped[0].terms])))
    elif (
        not names
        and (words_left := [w for w in missing if folded(w) not in ROMAN and not w.isdigit()])
        and len(kept_concepts) == 1
        and translated.operation is Operation.CHERCHER
        # A fact names what it counts (« Combien de blessés ? »): not a subject to restrict by.
        and every_word
    ):
        # A word of the question the model left out of every term is searched too: « SNCB »
        # stayed in the name « grèves SNCB », « école » was dropped (bench, 2026-10-29).
        # A number (« VI » of « GTA VI ») is never a subject of its own.
        word = words_left[0]
        # With the model's own terms for it, when one of its concepts holds a close word
        # (« prévenu » and « prévenir, avertir, waarschuwen » of a concept named « avait »).
        related = next(
            (c.terms for c in translated.concepts if any(_likeness(word, t) >= 5 for t in c.terms)),
            (),
        )
        terms = [t for t in related if folded(t) not in QUESTION_WORDS]
        kept_concepts = (*kept_concepts, Concept(word, _clean([word, *terms])))
    period = asked_period(question, today)
    # None named: the first stays, unless it is made of the words of a period.
    fallback = tuple(c for c in proposed[:1] if not _of_period(c))
    numbered_names = tuple(
        Concept(c.name, _clean([_numbered_phrase(t) for t in c.terms], PLACE_TERMS_MAX))
        for c in kept_concepts or fallback
    )
    kept = replace(translated, concepts=with_quoted(question, numbered_names), days=period)
    for code, language_names in LANGUAGE_WORDS.items():
        if words & set(language_names):
            return Translated(Operation.RESTREINDRE, (), code, period)
    return kept


def next_state(state: State, translated: Translated) -> State:
    """The concepts and language after the operation; the set follows them, without a model."""
    proposed = translated.concepts
    match translated.operation:
        case Operation.CHERCHER if proposed:
            # A new subject: a new set, in every language, over the period it names.
            # Three at most: a subject, a place, an aspect (« la situation financière des
            # hôpitaux en Flandre »).
            return State(proposed[:3], None, translated.days)
        case Operation.RESTREINDRE:
            # A place the set already holds restricts nothing more (« Seulement Bruxelles
            # Capitale » after the budget of the Région de Bruxelles-Capitale).
            added = [
                c for c in proposed[:1] if not any(_same_concept(c, s) for s in state.concepts)
            ]
            concepts = (*state.concepts, *added)[:CONCEPTS_MAX]
            return replace(
                state,
                concepts=concepts,
                language=translated.language or state.language,
                days=translated.days or state.days,
            )
        case Operation.ELARGIR if state.concepts and proposed:
            last = state.concepts[-1]
            widened = Concept(last.name, _clean([*last.terms, *proposed[0].terms]))
            return replace(state, concepts=(*state.concepts[:-1], widened))
        case _:
            return state


def only_a_period(question: str) -> bool:
    """A question that names a period and nothing else: « Les articles d'aujourd'hui ? » keeps
    the subject of the conversation, over that period."""
    return asked_period(question) is not None and not _named(question)


def changes_set(operation: Operation) -> bool:
    return operation in (Operation.CHERCHER, Operation.RESTREINDRE, Operation.ELARGIR)
