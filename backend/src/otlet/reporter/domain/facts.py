# SPDX-License-Identifier: AGPL-3.0-or-later
"""The answer to a question of fact (ADR-0044 §5, §6): lines cited by source, kept only when
their passage is in the article, and the agreement of the sources computed without a model.

On the bench of A2 the model gave 8 right answers of 10 with their context and never added
figures of different sources; but it labelled the agreement wrong 6 times of 11. The rule
below, on the same lines, was right 10 times of 11 (Joël, 2026-10-25).
"""

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from otlet.assistant.domain.terms import GlossaryEntry, folded

ARTICLES = 15
BODY_CHARS = 2500
# The passage of a line is compared on its first characters: the model may cut the end.
PASSAGE_PREFIX = 80
UNSPECIFIED = {"", "non precise", "non precisee", "inconnu"}
MEASURE_STOP = set("nombre total personnes selon dans pour avec sans des les une aux".split())
# Numbers written in words, in the three languages of the Veille: « quatre » at La DH and
# « vier » at Bruzz are the same four injured (bench of A2).
_UNITS = {
    "fr": "zero un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze"
    " seize dix-sept dix-huit dix-neuf vingt",
    "nl": "nul een twee drie vier vijf zes zeven acht negen tien elf twaalf dertien veertien"
    " vijftien zestien zeventien achttien negentien twintig",
    "en": "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen"
    " fifteen sixteen seventeen eighteen nineteen twenty",
}
NUMBER_WORDS = {
    word: str(n) for words in _UNITS.values() for n, word in enumerate(words.split())
} | {"une": "1", "trente": "30", "quarante": "40", "cinquante": "50", "cent": "100"}


class Agreement(StrEnum):
    CONCORDENT = "concordent"
    DIVERGENT = "divergent"
    PARTIEL = "partiel"
    UNE_SOURCE = "une source"
    ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class Article:
    """An item as the model reads it for a fact: numbered from 1 in the message."""

    item_id: str
    publisher: str
    text: str


@dataclass(frozen=True, slots=True)
class FactLine:
    item_id: str
    publisher: str
    figure: str
    measure: str
    when: str
    where: str
    passage: str
    # The figure is in the passage (its digits, or its words when it has none).
    figure_in_passage: bool


@dataclass(frozen=True, slots=True)
class Compared:
    """Two lines set against each other: same figure (agree) or not."""

    first: int
    second: int
    same: bool


@dataclass(frozen=True, slots=True)
class Fact:
    lines: tuple[FactLine, ...]
    agreement: Agreement
    compared: tuple[Compared, ...] = ()
    conclusion: str = ""
    # Lines the model gave whose passage is not in their article: dropped, counted.
    dropped: int = 0
    read: tuple[str, ...] = field(default=())


FACT_SYSTEM = (
    "Tu es le Reporter d'Otlet, un documentaliste. Réponds à la question de l'auteur à partir des "
    "articles numérotés, et d'eux seuls. Pour chaque chiffre ou date trouvé, une ligne : le "
    "numéro de l'article, le chiffre tel qu'écrit, ce qu'il mesure, quand, où, et l'extrait exact "
    "(copié mot pour mot, une phrase) qui le contient. N'additionne jamais des chiffres de sources "
    "différentes : elles peuvent compter les mêmes faits. Si deux chiffres ne portent pas sur la "
    "même période ou le même lieu, dis-le. « quand » et « où » sont obligatoires : la date ou le "
    "moment, et le lieu, de ce que le chiffre mesure, tels que l'article les donne "
    "(« non précisé » sinon). Lis la question avec la conversation : « Combien ? » après "
    "« des blessés ? » veut dire « combien de blessés ». Si aucun article ne répond, aucune "
    "ligne. Une phrase de conclusion courte, sans rien ajouter que les lignes ne disent."
)
FACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "lignes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "article": {"type": "integer"},
                    "chiffre": {"type": "string"},
                    "mesure": {"type": "string"},
                    "quand": {"type": "string"},
                    "ou": {"type": "string"},
                    "extrait": {"type": "string"},
                },
                "required": ["article", "chiffre", "mesure", "quand", "ou", "extrait"],
            },
        },
        "conclusion": {"type": "string"},
    },
    "required": ["lignes", "conclusion"],
}


QUESTION_STOP = set(
    "combien quand quel quelle quels quelles est-ce sont ont-ils elle elles leur leurs"
    " pour dans avec sans depuis selon cette cela".split()
)


def reading_order(question: str, texts: list[str]) -> list[int]:
    """The positions of the set in the order a fact reads them: first the items that hold the
    most words of the question (« alerte », « orange » for « Quand l'alerte orange a-t-elle
    commencé ? »), then the others in their order. The model reads only ARTICLES items: in a set
    of 126, the item that gave the answer on the bench was not among the first 15 by rank."""
    words = {
        w for w in re.findall(r"\w+", folded(question)) if len(w) > 3 and w not in QUESTION_STOP
    }

    def held(n: int) -> int:
        found = set(re.findall(r"\w+", folded(texts[n])))
        return len(words & found)

    return sorted(range(len(texts)), key=lambda n: -held(n))


def fact_message(history: list[str], question: str, articles: list[Article]) -> str:
    numbered = "\n\n".join(
        f"[{n}] {a.publisher} — {a.text[:BODY_CHARS]}" for n, a in enumerate(articles, 1)
    )
    context = "\n".join(f"Auteur : {q}" for q in history)
    return f"Conversation :\n{context}\n\nQuestion : {question}\n\nArticles :\n{numbered}"


def check_fact(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        return [f"not JSON: {error.msg}"]
    if not isinstance(data, dict) or not isinstance(data.get("lignes"), list):
        return ["lignes: a list is required"]
    return []


def _digits(text: str) -> str:
    """The digits of a figure, its number words read as digits (« quatre » → 4)."""
    words = [NUMBER_WORDS.get(w, w) for w in re.findall(r"[\w-]+", folded(text))]
    return "".join(ch for ch in " ".join(words) if ch.isdigit())


def read_fact(raw: str, articles: list[Article], glossary: list[GlossaryEntry]) -> Fact:
    """The lines whose passage is in their article, and their agreement (no model)."""
    data = json.loads(raw)
    lines: list[FactLine] = []
    dropped = 0
    for row in data["lignes"]:
        if not isinstance(row, dict):
            dropped += 1
            continue
        n = row.get("article")
        passage = str(row.get("extrait", ""))
        article = articles[n - 1] if isinstance(n, int) and 1 <= n <= len(articles) else None
        if article is None or not passage.strip():
            dropped += 1
            continue
        if folded(passage)[:PASSAGE_PREFIX] not in folded(article.text[:BODY_CHARS]):
            dropped += 1
            continue
        figure = str(row.get("chiffre", ""))
        # A publisher that ran the same story twice gives one line, not two (Le Monde updates
        # its live pages under new addresses: three times the same « 21 heures » on the bench).
        if any(
            line.publisher == article.publisher
            and folded(line.figure) == folded(figure)
            and folded(line.passage) == folded(passage)
            for line in lines
        ):
            continue
        digits = _digits(figure)
        lines.append(
            FactLine(
                item_id=article.item_id,
                publisher=article.publisher,
                figure=figure,
                measure=str(row.get("mesure", "")),
                when=str(row.get("quand", "")),
                where=str(row.get("ou", "")),
                passage=passage,
                figure_in_passage=(
                    digits in _digits(passage) if digits else folded(figure) in folded(passage)
                ),
            )
        )
    agreement, compared = concordance(lines, glossary)
    return Fact(
        lines=tuple(lines),
        agreement=agreement,
        compared=tuple(compared),
        conclusion=" ".join(str(data.get("conclusion", "")).split()),
        dropped=dropped,
        read=tuple(a.item_id for a in articles),
    )


def concordance(
    lines: list[FactLine], glossary: list[GlossaryEntry]
) -> tuple[Agreement, list[Compared]]:
    """The agreement of the sources, from the lines, without a model (ADR-0044 §6).

    Two lines of different sources are compared when they measure the same thing (the words of
    one measure all in the other), at the same moment (one « quand » holds the other) and at the
    same place (the same « où » once the glossary has made Brussel and Bruxelles one; a
    narrower place, « centre de Bruxelles », is a part and is not compared). « Non précisé »
    matches anything; a figure that is the moment itself (a date asked for) does not compare
    the moments; a vague figure (« la semaine prochaine ») is not set against a precise one.
    Every pair compared is returned, those that agree as those that differ."""

    def place(text: str) -> str:
        text = folded(text)
        for entry in glossary:
            if text in {folded(t) for t in entry.terms}:
                return folded(entry.terms[0])
        return text

    def words(text: str) -> set[str]:
        return {w for w in re.findall(r"\w+", folded(text)) if len(w) > 3 and w not in MEASURE_STOP}

    def same_measure(first: set[str], second: set[str]) -> bool:
        # The words of one measure all in the other: « blessés » and « gewonden (blessés) » are
        # the same measure; « température minimale » and « température maximale » are not
        # (Joël's question on the weather, 2026-10-25: 9 °C and 14 °C were said to diverge).
        return bool(first and second) and (first <= second or second <= first)

    def moment(line: FactLine) -> str:
        return "" if folded(line.when) == folded(line.figure) else folded(line.when)

    def value(text: str) -> str:
        return _digits(text) or folded(text)

    if not lines:
        return Agreement.ABSENT, []
    if len({line.publisher for line in lines}) == 1:
        return Agreement.UNE_SOURCE, []
    compared: list[Compared] = []
    for i, a in enumerate(lines):
        for j in range(i + 1, len(lines)):
            b = lines[j]
            if a.publisher == b.publisher or not same_measure(words(a.measure), words(b.measure)):
                continue
            ta, tb = moment(a), moment(b)
            if not (ta in UNSPECIFIED or tb in UNSPECIFIED or ta in tb or tb in ta):
                continue
            pa, pb = place(a.where), place(b.where)
            if not (pa in UNSPECIFIED or pb in UNSPECIFIED or pa == pb):
                continue
            if bool(_digits(a.figure)) != bool(_digits(b.figure)):
                continue
            compared.append(Compared(i, j, value(a.figure) == value(b.figure)))
    if any(not c.same for c in compared):
        return Agreement.DIVERGENT, compared
    if compared:
        return Agreement.CONCORDENT, compared
    return Agreement.PARTIEL, compared
