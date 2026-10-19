# SPDX-License-Identifier: AGPL-3.0-or-later
"""The measures of a draft (report « Audit qualité du moteur de génération », §7): the
guardrails of the product (otlet.writing.domain.guardrails) and what only the bench measures."""

import json
import re
from typing import Any

from otlet.writing.domain.guardrails import copying, fold, unsupported

# Judgements a neutral article attributes, or leaves out (the audit: 0.4 to 1 per 100 words).
JUDGEMENT = re.compile(
    r"\b(incontournables?|epoustouflant\w*|hilarant\w*|inoubliables?|parfait\w*|ideal\w*|"
    r"exceptionnel\w*|extraordinaire\w*|incroyable\w*|fascinant\w*|captivant\w*|magistral\w*|"
    r"remarquable\w*|impressionnant\w*|legendaire\w*|emblematique\w*|culte|reference du genre|"
    r"a ne pas manquer|chef d oeuvre|genial\w*|sublime\w*|spectaculaire\w*|brillant\w*|"
    r"inegale\w*|sans precedent|unique\w*|meilleur\w*|incomparable\w*|phenomenal\w*|"
    r"absolument|veritable\w*|vraiment|indeniabl\w*|incontestabl\w*)\b"
)
ENGLISH = re.compile(r"\b(the|and|of|with|is|are|was|which)\b")


def paragraphs_of(raw: str) -> tuple[list[str], int]:
    """The lead and the paragraphs of an answer, and its number of sections."""
    data = json.loads(raw)
    sections = data.get("sections", [])
    texts = [data.get("lead", "")] + [
        p.get("text", "") for s in sections for p in s.get("paragraphs", [])
    ]
    return texts, len(sections)


def measure(
    raw: str, sources: list[str], allowed: str, target_words: int, expect: dict[str, Any]
) -> dict[str, Any]:
    try:
        paragraphs, sections = paragraphs_of(raw)
    except (json.JSONDecodeError, AttributeError, TypeError):
        return {"valid": False}
    text = "\n".join(paragraphs)
    folded = fold(text)
    words = len(folded.split())
    source_text = fold(" ".join(sources))
    judgements = sorted(
        {m.group(0) for m in JUDGEMENT.finditer(folded) if m.group(0) not in source_text}
    )
    found = unsupported(paragraphs, sources, allowed)
    copied = copying(paragraphs, sources)
    items = expect.get("items", [])
    names = expect.get("names", [])
    return {
        "valid": True,
        "words": words,
        "sections": sections,
        "length_ratio": round(words / target_words, 2) if target_words else None,
        "unsupported": [f.text for f in found],
        "unsupported_per_100": round(100 * len(found) / max(words, 1), 2),
        "copy_share": copied.share,
        "copied_passages": len(copied.passages),
        "judgements": judgements,
        "judgements_per_100": round(100 * len(judgements) / max(words, 1), 2),
        "items_kept": None if not items else round(sum(i in folded for i in items) / len(items), 2),
        "names_kept": None if not names else round(sum(n in folded for n in names) / len(names), 2),
        "ids_in_text": bool(re.search(r"\bS\d+\b", text)),
        "english_words": len(ENGLISH.findall(folded)),
    }
