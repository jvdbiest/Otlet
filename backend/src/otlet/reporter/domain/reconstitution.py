# SPDX-License-Identifier: AGPL-3.0-or-later
"""« Reconstituer » (ADR-0044 §7, §8): a chronology or a synthesis from several articles, only when
the author asks for it.

The model says the form and the facets, extracts the lines of each facet, then writes an analysis
from the kept lines alone. The engine decides what is kept: a line stands on its passage in the
article, says something the question does not, adds no name or figure, and names no day the
calendar denies. The confidence is computed, never given by the model. On the bench of A2, in six
runs: right and rich on the riots in Brussels and the federal budget, « I do not find » on GMOs,
which is right, and weak on the start and end of a storm, which the confidence says.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from otlet.assistant.domain.terms import GlossaryEntry, folded
from otlet.reporter.domain.facts import (
    ARTICLES,
    BODY_CHARS,
    PASSAGE_PREFIX,
    Article,
    FactLine,
    concordance,
)

FACETS_MAX = 5
# « Proche » completes the matter, it never makes it (ADR-0044 §7).
MATTER_MIN = 5


class Confidence(StrEnum):
    FORTE = "forte"
    MOYENNE = "moyenne"
    FAIBLE = "faible"


@dataclass(frozen=True, slots=True)
class Facet:
    name: str
    question: str


@dataclass(frozen=True, slots=True)
class RebuiltLine:
    facet: int  # from 1
    item_id: str
    publisher: str
    dated: str  # the date of the article, ISO
    information: str
    when: str
    where: str
    passage: str
    # What the line says beyond its article, or a day the calendar denies: shown, not analysed.
    to_check: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Sentence:
    text: str
    lines: tuple[int, ...]  # numbers of the kept lines, from 1
    deduction: bool
    unsupported: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Reconstitution:
    requested: bool = False
    form: str = ""
    facets: tuple[Facet, ...] = ()
    lines: tuple[RebuiltLine, ...] = ()
    flagged: tuple[RebuiltLine, ...] = ()
    # What it comes to: the question answered first (Joël, 2026-10-31: « je vois comment la
    # conclusion est construite, mais pas quelle est la conclusion »); `sentences` detail it.
    answer: tuple[Sentence, ...] = ()
    sentences: tuple[Sentence, ...] = ()
    confidence: Confidence | None = None
    reasons: tuple[str, ...] = ()
    found: int = 0  # the articles of the set
    read: int = 0  # those read
    dropped: int = 0  # lines whose passage is not in their article
    errors: tuple[str, ...] = ()


FACETS_SYSTEM = (
    "Tu es le Reporter d'Otlet, un documentaliste. L'auteur demande une reconstitution à partir de "
    "plusieurs articles. Dis sa forme : « chronologie » (ce qui s'est passé, quand, où, comment "
    "cela a fini) ou « synthèse » (ce que disent les articles sur un thème, ce qu'ils mettent en "
    "avant, les points de vue). Puis découpe la question en 3 à 5 volets, chacun une question "
    "courte à laquelle des articles peuvent répondre. Pour une chronologie, par exemple « Début », "
    "« Lieux », « Fin » ; pour une synthèse, par exemple « Ce qui est dit », « Ce qui est mis en "
    "avant », "
    "« Critiques ». Les volets suivent la question de l'auteur, sans en ajouter d'autres."
)
FACETS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "forme": {"type": "string", "enum": ["chronologie", "synthèse"]},
        "volets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"nom": {"type": "string"}, "question": {"type": "string"}},
                "required": ["nom", "question"],
            },
        },
    },
    "required": ["forme", "volets"],
}
LINES_SYSTEM = (
    "Tu es le Reporter d'Otlet, un documentaliste. Pour le volet donné, relève dans les articles "
    "numérotés, et en eux seuls, ce qui y répond : une ligne par information, avec le numéro de "
    "l'article, l'information en quelques mots (avec ses chiffres tels qu'écrits), quand et où "
    "(tels que l'article les donne, « non précisé » sinon), et l'extrait exact qui la contient "
    "(copié mot pour mot, une phrase). Pour une synthèse, l'information est ce que l'article "
    "affirme ou met en avant, attribué à qui le dit. N'ajoute rien que les articles ne disent "
    "pas ; un volet sans réponse n'a aucune ligne. Ne garde d'un article que ce qui porte sur le "
    "sujet de la question. Une ligne dit ce que l'article apprend, jamais le nom du volet ni "
    "« n'est pas mentionné ». Pas de date ni de jour que l'article n'écrit pas : « vendredi » "
    "reste « vendredi »."
)
LINES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "lignes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "article": {"type": "integer"},
                    "information": {"type": "string"},
                    "quand": {"type": "string"},
                    "ou": {"type": "string"},
                    "extrait": {"type": "string"},
                },
                "required": ["article", "information", "quand", "ou", "extrait"],
            },
        }
    },
    "required": ["lignes"],
}
ANALYSIS_SYSTEM = (
    "Tu es le Reporter d'Otlet. À partir des lignes numérotées, et d'elles seules (tu ne vois pas "
    "les articles), écris deux choses. Dans « reponse », 2 à 4 phrases qui répondent directement à "
    "la question de l'auteur, comme à quelqu'un qui ne lira rien d'autre : la conclusion "
    "principale d'abord, puis chaque partie de la question ; dis clairement ce que les lignes ne "
    "permettent pas de dire, en parlant des articles lus, jamais des « lignes ». Pas une "
    "description des articles : la réponse. Chaque entrée est une seule phrase, sans redite. Dans "
    "« phrases », une analyse courte (3 à 6 phrases) qui détaille cette réponse. "
    "Pour chaque phrase, donne les numéros des lignes qui la portent, sans jamais les écrire dans "
    "le texte. Une déduction (ce que les "
    "lignes laissent penser sans le dire) est permise, mais marque-la comme déduction et "
    "formule-la comme telle (« semble », « laisse penser »). Aucun chiffre, aucune date, aucun "
    "lieu, aucun nom qui ne soit dans les lignes. Des moments différents désignent des événements "
    "différents, pas des sources en désaccord. Si les lignes ne suffisent pas pour répondre, "
    "dis-le en une phrase."
)
_SENTENCE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "texte": {"type": "string"},
        "lignes": {"type": "array", "items": {"type": "integer"}},
        "deduction": {"type": "boolean"},
    },
    "required": ["texte", "lignes", "deduction"],
}
ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reponse": {"type": "array", "items": _SENTENCE},
        "phrases": {"type": "array", "items": _SENTENCE},
    },
    "required": ["reponse", "phrases"],
}


def _list_of(raw: str, key: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        return [f"not JSON: {error.msg}"]
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        return [f"{key}: a list is required"]
    return []


def check_facets(raw: str) -> list[str]:
    return _list_of(raw, "volets")


def check_lines(raw: str) -> list[str]:
    return _list_of(raw, "lignes")


def check_analysis(raw: str) -> list[str]:
    return _list_of(raw, "reponse") + _list_of(raw, "phrases")


def read_facets(raw: str) -> tuple[str, tuple[Facet, ...]]:
    data = json.loads(raw)
    facets = tuple(
        Facet(str(row.get("nom", "")).strip(), str(row.get("question", "")).strip())
        for row in data["volets"]
        if isinstance(row, dict) and str(row.get("nom", "")).strip()
    )
    form = "synthèse" if folded(str(data.get("forme", ""))).startswith("synth") else "chronologie"
    return form, facets[:FACETS_MAX]


def chosen_evenly(items: list[Any]) -> list[Any]:
    """At most ARTICLES of a dated list, taken evenly along it: a chronology needs the whole
    period."""
    step = max(1.0, len(items) / ARTICLES)
    return [items[int(n * step)] for n in range(min(ARTICLES, len(items)))]


def numbered_articles(articles: list[Article], dates: dict[str, datetime]) -> str:
    return "\n\n".join(
        # The day, not the hour: « 23/10 20:52 » was taken for the end of a storm. With its year:
        # without it, a model dated articles of 2026 from « octobre 2023 » (Joël, 2026-10-31).
        f"[{n}] {a.publisher}, article du {dates[a.item_id]:%d/%m/%Y} — {a.text[:BODY_CHARS]}"
        for n, a in enumerate(articles, 1)
    )


def lines_message(question: str, facet: Facet, numbered: str) -> str:
    return (
        f"Question : {question}\n\nVolet : {facet.name} : {facet.question}\n\n"
        f"Articles :\n{numbered}"
    )


def analysis_message(question: str, lines: tuple[RebuiltLine, ...], today: date) -> str:
    listed = "\n".join(
        f"L{n} ({line.publisher}, article du {_day(line.dated)}) {line.information}"
        f" | quand : {line.when} | où : {line.where}"
        for n, line in enumerate(lines, 1)
    )
    return f"Nous sommes le {today:%d/%m/%Y}.\n\nQuestion : {question}\n\nLignes :\n{listed}"


def _day(dated: str) -> str:
    return datetime.fromisoformat(dated).strftime("%d/%m/%Y") if dated else "?"


# Words that may start with a capital without being a name.
COMMON = {
    folded(word)
    for word in (
        "Le La Les Un Une Des D'après Selon Après Avant Puis Ensuite Enfin Aucun Aucune Il Elle "
        "Ils Elles Ce Cette Ces Sources Plusieurs Certains Certaines Dans En Au Aux Du De Lors "
        "Alors Toutefois Cependant Mais Et Si Pour Par Sur L'alerte"
    ).split()
}


def unsupported(sentence: str, support: str) -> list[str]:
    """The figures and the names of a sentence that a text does not hold (ADR-0043 §10). The
    first word of a sentence is a capital by grammar: not checked."""
    held = folded(support)
    missing = [n for n in re.findall(r"\d+(?:[.,]\d+)?", sentence) if n not in support]
    for word in re.findall(r"(?<![.!?] )(?<!^)\b[A-ZÀ-Ý][\w'’-]+", sentence.strip()):
        name = folded(word.replace("’", "'"))
        if name not in COMMON and name.split("'")[-1] not in held:
            missing.append(word)
    return missing


DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
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


def dated_days(published: datetime, text: str) -> str:
    """The date of an article and the dates its weekdays can name: the last such day up to the
    article, or the next one after it (« samedi » written on Friday 23 October is the 24th)."""
    days = [published]
    for name in set(re.findall(r"\w+", folded(text))) & set(DAYS):
        back = (published.weekday() - DAYS.index(name)) % 7
        days += [published - timedelta(days=back), published + timedelta(days=(7 - back) % 7 or 7)]
    return " ".join(f"{d.day} {MONTHS[d.month - 1]} {DAYS[d.weekday()]}" for d in days)


def wrong_days(text: str, year: int) -> list[str]:
    """« mercredi 23 octobre » when the 23rd of October is a Friday: a day the calendar denies."""
    out = []
    for day, number, month in re.findall(r"(\w+) (\d{1,2}) (\w+)", folded(text)):
        if day in DAYS and month in MONTHS:
            try:
                real = datetime(year, MONTHS.index(month) + 1, int(number)).weekday()
            except ValueError:
                continue
            if DAYS[real] != day:
                out.append(f"{day} {number} {month} (un {DAYS[real]})")
    return out


def _added(information: str, text: str, glossary: list[GlossaryEntry], asked: str) -> list[str]:
    """What a line says beyond its article. The glossary counts (« Bruxelles » is in an article
    that writes « Brussel »), and so do the words of the question and its facets."""
    held = f" {folded(text)} "
    same = [
        term
        for entry in glossary
        if any(f" {folded(t)} " in held for t in entry.terms)
        for term in entry.terms
    ]
    return unsupported(information, " ".join([text, *same, asked]))


def _says_nothing(information: str, passage: str, asked: str) -> bool:
    """A line that tells nothing of its passage: only the words of the question and its facets
    (« Lieux traversés par la tempête Austen »), or what the article does not say."""
    if "pas mentionn" in folded(information):
        return True
    words = {w for w in re.findall(r"\w+", folded(information)) if len(w) > 3}
    new = words - set(re.findall(r"\w+", folded(asked)))
    return not new & set(re.findall(r"\w+", folded(passage)))


def read_lines(
    raw: str,
    facet: int,
    articles: list[Article],
    dates: dict[str, datetime],
    asked: str,
    glossary: list[GlossaryEntry],
    kept: list[RebuiltLine],
) -> tuple[list[RebuiltLine], list[RebuiltLine], int]:
    """The rules of lines (ADR-0044 §8): the new kept lines, those to check, and how many had no
    passage in their article. `kept`: the lines of the earlier facets, since one passage gives
    one line."""
    new: list[RebuiltLine] = []
    flagged: list[RebuiltLine] = []
    dropped = 0
    for row in json.loads(raw)["lignes"]:
        if not isinstance(row, dict):
            dropped += 1
            continue
        n = row.get("article")
        passage = str(row.get("extrait", ""))
        article = articles[n - 1] if isinstance(n, int) and 1 <= n <= len(articles) else None
        text = "" if article is None else article.text[:BODY_CHARS]
        if article is None or not passage.strip():
            dropped += 1
            continue
        if folded(passage)[:PASSAGE_PREFIX] not in folded(text):
            dropped += 1
            continue
        information = " ".join(str(row.get("information", "")).split())
        if _says_nothing(information, passage, asked):
            continue
        day = dates[article.item_id]
        when, where = str(row.get("quand", "")), str(row.get("ou", ""))
        extra = _added(information, text, glossary, asked)
        extra += wrong_days(f"{information} {when}", day.year)
        line = RebuiltLine(
            facet,
            article.item_id,
            article.publisher,
            day.isoformat(),
            information,
            when,
            where,
            passage,
            tuple(extra),
        )
        if extra:
            flagged.append(line)
        elif not any(_same_line(line, other) for other in (*kept, *new)):
            new.append(line)
    return new, flagged, dropped


def _same_line(line: RebuiltLine, other: RebuiltLine) -> bool:
    """One passage gives one line. A publisher that updates its story under new addresses says
    it once too: the budget gave « Retour à l'objectif de 10 milliards » three times."""
    if line.publisher != other.publisher:
        return False
    return folded(line.passage) == folded(other.passage) or (
        folded(line.information) == folded(other.information)
    )


def confidence(
    form: str,
    facets: tuple[Facet, ...],
    lines: tuple[RebuiltLine, ...],
    glossary: list[GlossaryEntry],
) -> tuple[Confidence, tuple[str, ...]]:
    """Forte, moyenne or faible, with its reasons. Figures are set against each other only in a
    chronology: in a synthesis, 10 billions by 2029 and 4 billions in 2027 are two proposals, not
    two sources in disagreement."""
    level = Confidence.FORTE
    reasons = []
    for number, facet in enumerate(facets, 1):
        here = [line for line in lines if line.facet == number]
        sources = {line.publisher for line in here}
        pairs = (
            [
                FactLine(
                    line.item_id,
                    line.publisher,
                    line.information,
                    line.information,
                    line.when,
                    line.where,
                    line.passage,
                    True,
                )
                for line in here
                if any(ch.isdigit() for ch in line.information)
            ]
            if form == "chronologie"
            else []
        )
        _, compared = concordance(pairs, glossary)
        diverging = next((c for c in compared if not c.same), None)
        if not here:
            reasons.append(f"« {facet.name} » : aucune source")
            level = Confidence.FAIBLE
        elif diverging is not None:
            reasons.append(
                f"« {facet.name} » : les sources divergent ({pairs[diverging.first].figure}"
                f" contre {pairs[diverging.second].figure})"
            )
            level = Confidence.FAIBLE
        elif len(sources) == 1:
            reasons.append(f"« {facet.name} » ne tient qu'à une source ({next(iter(sources))})")
            if level is Confidence.FORTE:
                level = Confidence.MOYENNE
    return level, tuple(reasons)


# « (L1, L6) » in a sentence: the numbers belong to its lines, not to its text.
LINE_NUMBERS = re.compile(
    r"\s*(?:,\s*)?(?:comme indiqué dans\s+)?\(?\b(?:L\d+(?:\s*,\s*L\d+)*"
    r"|(?:les\s+)?lignes?\s+\d+(?:\s*(?:,|et)\s*\d+)*)\)?",
    re.IGNORECASE,
)
# The answer stops at two sentences or more: asked for one sentence an entry, a model may still
# write the whole answer in the first, then say it again in the second (bench, 2026-10-31).
ANSWER_ENOUGH = 2
OUR_WORD = re.compile(r"\b([Ll]es) lignes\b")
A_YEAR = re.compile(r"\b(?:19|20)\d\d\b")


def read_analysis(
    raw: str, lines: tuple[RebuiltLine, ...], articles: list[Article]
) -> tuple[tuple[Sentence, ...], tuple[Sentence, ...]]:
    """The answer and the analysis, each sentence with its lines."""
    answer: list[Sentence] = []
    for sentence in _sentences(raw, "reponse", lines, articles):
        written = sum(len(re.findall(r"[.!?…](?:\s|$)", s.text)) for s in answer)
        if written >= ANSWER_ENOUGH:
            break
        answer.append(sentence)
    return tuple(answer), _sentences(raw, "phrases", lines, articles)


def _sentences(
    raw: str, key: str, lines: tuple[RebuiltLine, ...], articles: list[Article]
) -> tuple[Sentence, ...]:
    """Each sentence with what it says that its articles do not: it may use what the cited
    articles hold, their dates, and the dates their weekdays name."""
    texts = {a.item_id: a.text[:BODY_CHARS] for a in articles}
    out = []
    for row in json.loads(raw)[key]:
        if not isinstance(row, dict) or not str(row.get("texte", "")).strip():
            continue
        text = " ".join(LINE_NUMBERS.sub("", str(row["texte"])).split())
        # « Lignes » is a word of the prompt: the reader knows articles.
        text = OUR_WORD.sub(r"\1 articles lus", text)
        numbers = tuple(
            n
            for n in row.get("lignes") or []
            if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= len(lines)
        )
        cited = [lines[n - 1] for n in numbers]
        support = " ".join(
            f"{texts.get(line.item_id, '')} {line.publisher} "
            + dated_days(datetime.fromisoformat(line.dated), texts.get(line.item_id, ""))
            for line in cited
        )
        year = datetime.fromisoformat(cited[0].dated).year if cited else 0
        # A year stands on the lines themselves and their dates: an article that mentions 2023 in
        # passing does not date what the sentence says.
        said = " ".join(
            f"{line.information} {line.when} {line.where} {line.passage} {line.dated}"
            for line in cited
        )
        years = [y for y in A_YEAR.findall(text) if y not in said]
        missing = (
            [*unsupported(text, support), *wrong_days(text, year), *years]
            if cited
            else ["aucune ligne citée"]
        )
        out.append(Sentence(text, numbers, bool(row.get("deduction")), tuple(missing)))
    return tuple(out)
