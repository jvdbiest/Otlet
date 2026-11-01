# SPDX-License-Identifier: AGPL-3.0-or-later
"""How close a version is to each of its sources (U05, ADR-0046): the check measured by P02b.

For each sentence of the text, the cosine of the nearest sentence of the source; the score is the
highest mean over WINDOW consecutive sentences, so that a passage taken from a source is not
diluted by the rest of the text. In the same language, the longest common subsequence of words
counts too; across languages, the semantic score alone (DR4).

This says how close a text is to its source, never whether it is faithful to it (FOND1): a
version that passes is not verified. The splitting and the normalisation are those of the measure:
changing them changes what the thresholds mean.
"""

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from otlet.writing.domain.guardrails import start_of

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
WINDOW = 5
# Fixed before the measure, confirmed on articles never seen (docs/spikes/P02b.md).
SAME_LANGUAGE = 0.85
OTHER_LANGUAGE = 0.80
LEXICAL = 0.70
PASSAGES_MAX = 10
EXCERPT_CHARS = 300
JUSTIFICATION_MIN = 10
JUSTIFICATION_MAX = 1000

SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])")
REFERENCES = re.compile(r"\s*\[\d+(?:\s*,\s*\d+)*\]")

Encode = Callable[[Sequence[str]], Sequence[Sequence[float]]]
Gate = Literal["open", "pending", "blocked"]


class TooClose(Exception):
    """A version cannot go out yet: it is too close to a source, or not checked yet."""

    def __init__(self, gate: Gate) -> None:
        super().__init__(gate)
        self.gate = gate


@dataclass(frozen=True, slots=True)
class Source:
    title: str
    url: str | None
    language: str | None
    text: str


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE.split(text) if s.strip()]


def words(text: str) -> list[str]:
    return re.findall(r"[\w’']+", unicodedata.normalize("NFC", text.lower()))


def common_subsequence(a: Sequence[str], b: Sequence[str]) -> int:
    """The length of the longest common subsequence of two lists of words, bit by bit: a source
    has thousands of words."""
    masks: dict[str, int] = {}
    for position, word in enumerate(a):
        masks[word] = masks.get(word, 0) | (1 << position)
    full = (1 << len(a)) - 1
    row = full
    for word in b:
        match = row & masks.get(word, 0)
        row = ((row + match) | (row - match)) & full
    return len(a) - row.bit_count()


def lexical_score(source: str, text: str) -> float:
    theirs, ours = words(source), words(text)
    return common_subsequence(theirs, ours) / len(ours) if ours else 0.0


def _family(language: str | None) -> str | None:
    return language[:2].lower() if language else None


def _nearest(
    ours: Sequence[Sequence[float]], theirs: Sequence[Sequence[float]]
) -> list[tuple[float, int]]:
    """For each of our sentences, the cosine of the nearest of theirs, and which one."""
    found = []
    for vector in ours:
        best, where = -1.0, 0
        for index, other in enumerate(theirs):
            cosine = sum(x * y for x, y in zip(vector, other, strict=True))
            if cosine > best:
                best, where = cosine, index
        found.append((best, where))
    return found


def _window(cosines: Sequence[float]) -> tuple[float, list[int]]:
    """The highest mean over WINDOW consecutive sentences, and where each such window starts."""
    if not cosines:
        return 0.0, []
    if len(cosines) <= WINDOW:
        return sum(cosines) / len(cosines), [0]
    means = [
        sum(cosines[start : start + WINDOW]) / WINDOW for start in range(len(cosines) - WINDOW + 1)
    ]
    best = max(means)
    return best, [start for start, mean in enumerate(means) if mean == best]


def _excerpt(text: str) -> str:
    return " ".join(text.split())[:EXCERPT_CHARS]


def check(
    title: str,
    paragraphs: Sequence[str],
    language: str | None,
    sources: Sequence[Source],
    encode: Encode,
) -> dict[str, Any]:
    """The report kept with the version: each source with its scores, and for those too close the
    passages of the version beside the sentences of the source they are close to."""
    cleaned = [REFERENCES.sub("", p) for p in paragraphs]
    text = f"{title}. " + "\n".join(cleaned)
    ours = sentences(text) or [text]
    our_vectors = encode(ours)
    mine = _family(language)
    report = []
    for source in sources:
        body = f"{source.title}\n{source.text}"
        theirs = sentences(body) or [body]
        nearest = _nearest(our_vectors, encode(theirs))
        cosines = [cosine for cosine, _ in nearest]
        score, starts = _window(cosines)
        family = _family(source.language)
        same = family is None or mine is None or family == mine
        limit = SAME_LANGUAGE if same else OTHER_LANGUAGE
        lexical = lexical_score(body, text) if same else 0.0
        too_close = score >= limit or (same and lexical >= LEXICAL)
        passages = []
        if too_close:
            # The sentences of the windows at the highest score, nearest first.
            indexes = sorted(
                {i for start in starts for i in range(start, min(start + WINDOW, len(ours)))},
                key=lambda i: -cosines[i],
            )
            for index in indexes[:PASSAGES_MAX]:
                passages.append(
                    {
                        "paragraph": _paragraph_of(ours[index], cleaned),
                        "sentence": _excerpt(ours[index]),
                        "source_sentence": _excerpt(theirs[nearest[index][1]]),
                        "cosine": round(cosines[index], 3),
                    }
                )
        report.append(
            {
                "title": source.title,
                "url": source.url,
                "languages": "same" if same else "other",
                "score": round(score, 3),
                "limit": limit,
                "lexical": round(lexical, 3),
                "too_close": too_close,
                "passages": passages,
            }
        )
    return {
        "status": "checked",
        "blocked": any(s["too_close"] for s in report),
        "model": MODEL,
        "sources": report,
    }


def _paragraph_of(sentence: str, paragraphs: Sequence[str]) -> str:
    """The start of the paragraph that holds a sentence, as the interface finds it; none for the
    title."""
    for paragraph in paragraphs:
        if sentence[:60] in paragraph:
            return start_of(paragraph)
    return ""


def gate_of(
    has_brief: bool, proximity: dict[str, Any] | None, override: dict[str, Any] | None
) -> Gate:
    """Whether a version can go out. An article without a brief has no source to compare with. A
    check that failed lets it through with a warning: it must not lock the author out."""
    if not has_brief or override is not None:
        return "open"
    if proximity is None:
        return "pending"
    return "blocked" if proximity.get("blocked") is True else "open"
