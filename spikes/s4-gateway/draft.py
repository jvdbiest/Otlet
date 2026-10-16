# SPDX-License-Identifier: AGPL-3.0-or-later
"""S4: briefs and the structured output schema of the "redaction" usage (docs/spikes/S4.md §3.2).

The 50 briefs come from the S5 corpus (CC0-1.0): the subject of a topic, and three sources,
the source text, its translation and the independent text in the same language.
"""

from __future__ import annotations

import glob
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

HERE = Path(__file__).parent
CORPUS = HERE.parent / "s5-similarity" / "corpus"


class Paragraph(BaseModel):
    text: str = Field(min_length=20)
    source_ids: list[str] = Field(min_length=1)


class Section(BaseModel):
    heading: str = Field(min_length=3)
    paragraphs: list[Paragraph] = Field(min_length=1)


class ArticleDraft(BaseModel):
    title: str = Field(min_length=5)
    lead: str = Field(min_length=20)
    sections: list[Section] = Field(min_length=2, max_length=4)
    sources_used: list[str] = Field(min_length=1)


@dataclass(frozen=True)
class Brief:
    number: int
    language: str
    subject: str
    sources: dict[str, str]  # id -> text


def briefs() -> list[Brief]:
    result = []
    for path in sorted(glob.glob(str(CORPUS / "topics-*.json"))):
        for topic in json.loads(Path(path).read_text(encoding="utf-8")):
            result.append(Brief(
                number=topic["id"],
                language=topic["lang"],
                subject=topic["subject"],
                sources={"S1": topic["source"], "S2": topic["translation"], "S3": topic["independent_same"]},
            ))
    return result


def prompt(brief: Brief) -> list[dict[str, str]]:
    language = "français" if brief.language == "fr" else "English"
    sources = "\n\n".join(f"[{key}] {text}" for key, text in brief.sources.items())
    system = (
        "You write a short news article draft from the sources given, without copying them. "
        "Answer with one JSON object only, matching the schema: title, lead, 2 to 4 sections "
        "(heading, paragraphs), each paragraph with the ids of the sources that support it "
        "(source_ids, taken from the ids given), and sources_used."
    )
    user = f"Language: {language}\nSubject: {brief.subject}\n\nSources:\n{sources}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def validate(raw: str, brief: Brief) -> tuple[ArticleDraft | None, list[str]]:
    """Schema, then every source id must belong to the brief."""
    try:
        draft = ArticleDraft.model_validate_json(raw)
    except ValidationError as error:
        return None, [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()][:10]
    known = set(brief.sources)
    cited = {i for s in draft.sections for p in s.paragraphs for i in p.source_ids} | set(draft.sources_used)
    unknown = sorted(cited - known)
    if unknown:
        return None, [f"unknown source ids: {', '.join(unknown)}; allowed: {', '.join(sorted(known))}"]
    return draft, []


SCHEMA = ArticleDraft.model_json_schema()
