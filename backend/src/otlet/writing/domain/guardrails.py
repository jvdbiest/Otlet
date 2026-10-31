# SPDX-License-Identifier: AGPL-3.0-or-later
"""The guardrails of a draft, first batch of U05 (Joël, 2026-10-19, after the quality audit):
checks of the content after the model wrote it, which no prompt replaces.

- `unsupported`: the proper names, dates and numbers of the draft that its sources never write.
  The audit found « Stephen King » in 5 of 19 drafts of a top 10 whose source never names him:
  a model fills in with what it knows. A finding is a clue for the author, not a proof. A
  place counts as written under any of its forms (PLACES).
- `copying`: the passages taken word for word from a source, and the share of the draft they
  make (some models copy 40 to 60 % of their sequences of 8 words).

Both are lexical and deterministic: the same draft gives the same findings, on any machine."""

import re
import unicodedata
from dataclasses import dataclass

# A sequence of this many words found in a source is copied; one this long is a copied
# passage worth showing (a sentence, roughly).
COPY_GRAM = 8
COPY_PASSAGE = 12
# A passage this long is no longer a shared turn of phrase: it is refused, then taken out.
COPY_LONG = 25
# Words with a capital that start sentences or are capitalized by habit, not names.
NOT_NAMES = frozenset(
    """le la les l un une des de du d au aux ce cet cette ces il elle ils elles on en dans pour
    par sur avec mais et ou si selon apres avant depuis lors son sa ses leur leurs qui que quand
    comme a pourtant ainsi alors enfin entre malgre notamment toutefois cependant contrairement
    voici voila chaque tous toutes tout toute nous vous je tu y ne pas plus aussi meme deja
    puis donc car or ni sans sous vers chez parmi grace face lorsque puisque bien enfin certes
    the a an of and in on for with by to at from this that these those it its his her
    their""".split()
)
NAME = re.compile(
    r"[A-ZÀ-ÖØ-Þ][\w'’-]*(?:\s+(?:de |du |des |la |le |von |van |da |di )?[A-ZÀ-ÖØ-Þ][\w'’-]*)*"
)
POSSESSIVE = re.compile(r"['’]s$")
ELISION = re.compile(r"^(?:[ldjmnstcq]|qu|jusqu|lorsqu|puisqu)['’]", re.I)
# The forms of a place, folded: its name, its people, its adjective, its English name. A place
# the draft names is known when a source writes one of them: « en France » rewords « sur le
# territoire français », « en Belgique » « des Belges » (Joël, 2026-10-24: no inventions).
# Short or ambiguous forms are left out (« us », « eu », « ue »).
PLACES = tuple(
    frozenset(forms.strip().split(","))
    for forms in """
    france,francais,francaise,francaises,french
    belgique,belge,belges,belgium,belgian
    wallonie,wallon,wallonne,wallons,wallonia
    flandre,flandres,flamand,flamande,flamands,flanders,flemish
    bruxelles,bruxellois,bruxelloise,brussels
    bruges,brugge
    gand,gent,ghent
    anvers,antwerpen,antwerp
    liege,luik
    louvain,leuven
    europe,europeen,europeenne,europeens,europeennes,european
    allemagne,allemand,allemande,allemands,allemandes,germany,german
    angleterre,anglais,anglaise,england,english
    chine,chinois,chinoise,chinoises,china,chinese
    japon,japonais,japonaise,japonaises,japan,japanese
    russie,russe,russes,russia,russian
    ukraine,ukrainien,ukrainienne,ukrainiens,ukrainian
    italie,italien,italienne,italiens,italy,italian
    espagne,espagnol,espagnole,espagnols,spain,spanish
    suisse,suisses,switzerland,swiss
    canada,canadien,canadienne,canadiens,canadian
    inde,indien,indienne,indiens,india,indian
    israel,israelien,israelienne,israeliens,israeli
    autriche,autrichien,autrichienne,austria,austrian
    californie,californien,californienne,california
    etats unis,americain,americaine,americains,americaines,united states,american
    royaume uni,britannique,britanniques,united kingdom,british,uk
    pays bas,neerlandais,neerlandaise,netherlands,dutch
    cisjordanie,west bank""".strip().splitlines()
)
NUMBER = re.compile(r"\d[\d\s  .,]*\d|\d")


@dataclass(frozen=True, slots=True)
class Finding:
    kind: str  # "name", "date" or "number"
    text: str  # as the draft writes it
    paragraph: str  # the start of the paragraph that holds it, to find it again


@dataclass(frozen=True, slots=True)
class Copying:
    share: float  # of the sequences of COPY_GRAM words of the draft, those found in a source
    # (the start of its paragraph, its first words, its length in words), for each passage
    passages: tuple[tuple[str, str, int], ...]


def fold(text: str) -> str:
    """Lower case, no accents, single spaces: how texts are compared."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", text))


def _digits(text: str) -> str:
    return re.sub(r"[\s  ]", "", text)


def start_of(paragraph: str) -> str:
    """How a paragraph is named in a finding: its first words, as the interface finds it."""
    return paragraph.strip()[:60]


def _names(paragraph: str) -> list[str]:
    found = []
    for match in NAME.finditer(paragraph):
        name = ELISION.sub("", match.group(0)).strip(" -'’")
        words = [POSSESSIVE.sub("", w) for w in name.split()]
        while words and fold(words[0]) in NOT_NAMES:
            words = words[1:]
        if not words or not words[0][:1].isupper() or len("".join(words)) < 2:
            continue
        name = " ".join(words)
        at_start = match.start() == 0 or paragraph[: match.start()].rstrip()[-1:] in '.!?:«"—'
        if at_start and len(words) == 1:
            continue  # one capitalized word opening a sentence: most often a plain word
        found.append(name)
    return found


def unsupported(paragraphs: list[str], sources: list[str], allowed: str = "") -> list[Finding]:
    """The names, dates and numbers of `paragraphs` that neither the sources nor `allowed` (what
    the author wrote in the brief) contain, once each, in order."""
    reference = " " + fold(" ".join([*sources, allowed])) + " "
    reference_digits = _digits(" ".join([*sources, allowed]))
    findings: list[Finding] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        for name in _names(paragraph):
            folded = fold(name)
            parts = [p for p in folded.split() if len(p) > 3]
            known = (
                f" {folded} " in reference
                or (len(parts) > 1 and all(f" {p} " in reference for p in parts))
                or any(
                    folded in forms and any(f" {form} " in reference for form in forms)
                    for forms in PLACES
                )
            )
            if not known and folded not in seen:
                seen.add(folded)
                findings.append(Finding("name", name, start_of(paragraph)))
        for match in NUMBER.finditer(paragraph):
            raw = match.group(0).strip(" .,  ")
            digits = _digits(raw)
            if len(digits) < 2 or digits in seen:
                continue
            if digits in reference_digits or digits.replace(",", ".") in reference_digits:
                continue
            seen.add(digits)
            year = len(raw) == 4 and raw.isdigit() and 1000 <= int(raw) <= 2100
            findings.append(Finding("date" if year else "number", raw, start_of(paragraph)))
    return findings


def copied_sequences(sources: list[str]) -> frozenset[tuple[str, ...]]:
    """The sequences of COPY_GRAM words of the sources."""
    grams: set[tuple[str, ...]] = set()
    for source in sources:
        words = fold(source).split()
        grams |= {tuple(words[i : i + COPY_GRAM]) for i in range(len(words) - COPY_GRAM + 1)}
    return frozenset(grams)


def longest_copy(paragraph: str, grams: frozenset[tuple[str, ...]]) -> int:
    """The length in words of the longest passage of a paragraph found in a source."""
    words = fold(paragraph).split()
    longest = run = 0
    for i in range(len(words) - COPY_GRAM + 1):
        run = run + 1 if tuple(words[i : i + COPY_GRAM]) in grams else 0
        longest = max(longest, run)
    return longest + COPY_GRAM - 1 if longest else 0


def without_copied(paragraph: str, grams: frozenset[tuple[str, ...]]) -> tuple[str, list[str]]:
    """A paragraph with a long copied passage, without the sentences of that passage; and them."""
    if longest_copy(paragraph, grams) < COPY_LONG:
        return paragraph, []
    kept: list[str] = []
    removed: list[str] = []
    for sentence in re.split(r"(?<=[.!?…])\s+", paragraph):
        words = fold(sentence).split()
        sequences = [tuple(words[i : i + COPY_GRAM]) for i in range(len(words) - COPY_GRAM + 1)]
        hits = sum(sequence in grams for sequence in sequences)
        (removed if sequences and hits / len(sequences) >= 0.8 else kept).append(sentence)
    return " ".join(kept), removed


def copying(paragraphs: list[str], sources: list[str]) -> Copying:
    """The share of the draft's sequences of COPY_GRAM words found in a source, and its copied
    passages of COPY_PASSAGE words or more."""
    grams = copied_sequences(sources)
    total = copied = 0
    passages: list[tuple[str, str, int]] = []
    for paragraph in paragraphs:
        words = fold(paragraph).split()
        hits = [tuple(words[i : i + COPY_GRAM]) in grams for i in range(len(words) - COPY_GRAM + 1)]
        total += len(hits)
        copied += sum(hits)
        run_start = None
        for i, hit in enumerate([*hits, False]):
            if hit and run_start is None:
                run_start = i
            elif not hit and run_start is not None:
                length = i - run_start + COPY_GRAM - 1
                if length >= COPY_PASSAGE:
                    # The same words as fold() reads them, as the paragraph writes them.
                    spans = [m.span() for m in re.finditer(r"\w+", paragraph)]
                    last = spans[min(run_start + 9, len(spans) - 1)]
                    excerpt = paragraph[spans[run_start][0] : last[1]]
                    passages.append((start_of(paragraph), excerpt, length))
                run_start = None
    return Copying(round(copied / total, 3) if total else 0.0, tuple(passages))
