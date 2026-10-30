# SPDX-License-Identifier: AGPL-3.0-or-later
"""The part of a long source a draft receives: its opening, then its paragraphs the most about
the subject of the brief, in their order.

Cut at its start, a source lost what corrected the rest. On the brief « piratage IA » (bench of
2026-10-30), 14 sources shared the room and each sent its first 2,190 characters: the draft
linked Japan's call to AI, when the source rules that out further down. Lexical and
deterministic, like the guardrails: the same brief gives the same passages, on any machine.
"""

import re

from otlet.writing.domain.guardrails import fold

# Words by their first letters: « pirates » is « piratage ».
STEM = 5
# A word of the subject weighs more than a word several sources of the brief share.
SUBJECT_WEIGHT = 3.0
SHARED_WEIGHT = 1.0
# Shared by this many sources at least, and by no more than this share of them: a word nearly
# all of them write says nothing about a paragraph.
SHARED_MIN = 3
SHARED_SHARE = 0.7
PARAGRAPH_MIN_WORDS = 8
OPENING_MIN_WORDS = 25
# A text without paragraphs is read by groups of sentences of this size.
PARAGRAPH_MAX_CHARS = 1200
GAP = " […] "
STOP = frozenset(
    """dans pour plus avec cette mais sont comme leur leurs elle elles ils nous vous aussi tout
    tous toute toutes faire fait etre avoir avait ont sans sous entre apres avant depuis encore
    deux quel quels quelle quelles les des une qui que quoi dont lors selon alors ainsi meme tres
    bien peut pourrait seront etait ete cela celui celle ceux ces ses aux par sur est actualite
    actualites semaine article articles lire suite voir publicite commenter connexion le la de du
    un et ou en au a l d ce this that with from have their will would about were been they them
    over into than more the of and in on for to at is deze voor niet maar zijn naar door meer ook
    werd heeft hebben worden het een van""".split()
)
# What a page adds around an article.
NOISE = re.compile(r"^\W*(à lire aussi|a lire aussi|lire aussi|suivez|publicité)\b", re.IGNORECASE)


def _stems(text: str, shortest: int) -> set[str]:
    words = fold(text).split()
    return {w[:STEM] for w in words if len(w) >= shortest and w not in STOP and not w.isdigit()}


def words_of(text: str) -> set[str]:
    """The stems of a text, without its short and common words."""
    return _stems(text, 4)


def subject_of(text: str) -> set[str]:
    """The stems of a subject, which keeps its short words: « IA », « PS5 »."""
    return _stems(text, 2)


def vocabulary(subject: str, texts: list[str]) -> dict[str, float]:
    """The words a paragraph is weighed by: the subject, and what several sources share."""
    counts: dict[str, int] = {}
    for text in texts:
        for word in words_of(text):
            counts[word] = counts.get(word, 0) + 1
    highest = max(SHARED_MIN, int(len(texts) * SHARED_SHARE))
    found = {w: SHARED_WEIGHT for w, n in counts.items() if SHARED_MIN <= n <= highest}
    found.update(dict.fromkeys(subject_of(subject), SUBJECT_WEIGHT))
    return found


def _paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    for line in re.split(r"\n+", text):
        paragraph = " ".join(line.split())
        if len(paragraph) <= PARAGRAPH_MAX_CHARS:
            paragraphs.append(paragraph)
            continue
        group = ""
        for sentence in re.split(r"(?<=[.!?…])\s+", paragraph):
            if group and len(group) + len(sentence) > PARAGRAPH_MAX_CHARS // 2:
                paragraphs.append(group)
                group = ""
            group = f"{group} {sentence}".strip()
        paragraphs.append(group)
    return [p for p in paragraphs if len(p.split()) >= PARAGRAPH_MIN_WORDS and not NOISE.match(p)]


def passages(text: str, room: int, weights: dict[str, float]) -> str:
    """At most `room` characters of a text: its first real paragraph, then the paragraphs that
    weigh the most, in their order, « […] » where some are left out. A text without paragraphs
    to choose from is cut at its start."""
    paragraphs = _paragraphs(text)
    opening = next(
        (i for i, p in enumerate(paragraphs) if len(p.split()) >= OPENING_MIN_WORDS), None
    )
    scores = {
        i: sum(weights.get(w, 0.0) for w in words_of(p) | (subject_of(p) & weights.keys()))
        / max(len(p.split()), 12) ** 0.5
        for i, p in enumerate(paragraphs)
    }
    by_weight = sorted(scores, key=lambda i: (-scores[i], i))
    kept: set[int] = set()
    used = 0
    for index in ([] if opening is None else [opening]) + by_weight:
        size = len(paragraphs[index]) + len(GAP)
        if index not in kept and used + size <= room:
            kept.add(index)
            used += size
    if not kept:
        return " ".join(text.split())[:room].rstrip()
    written = ""
    last = None
    for index in sorted(kept):
        written += paragraphs[index] if last is None else (" " if index == last + 1 else GAP)
        if last is not None:
            written += paragraphs[index]
        last = index
    return written
