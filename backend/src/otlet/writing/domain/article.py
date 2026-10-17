# SPDX-License-Identifier: AGPL-3.0-or-later
"""Articles and their versions (U04, F-RED-04): a version is never changed, a new one is made."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Version:
    number: int
    title: str
    document: dict[str, Any]  # « Document plateforme v1 » (ADR-0023)
    origin: str  # ia: written by a model; humain: by a person
    provider_kind: str | None
    model: str | None
    prompt_version: str | None
    cut_sources: tuple[str, ...]  # titles of the items whose text was cut to fit the model
    unused_sources: tuple[str, ...]  # titles of the items of the brief the draft does not cite
    context_overflow: bool  # more tokens than the window: the start may have been dropped
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Article:
    id: UUID
    brief_id: UUID | None
    title: str
    created_at: datetime
    updated_at: datetime
    versions: tuple[Version, ...] = field(default=())  # the latest last


@dataclass(frozen=True, slots=True)
class Generation:
    """The request of a draft for a brief, run by the worker."""

    id: UUID
    brief_id: UUID
    status: str  # running, done, failed
    error: str | None  # why it failed: no_profile, budget, refused, invalid, quota, unavailable…
    article_id: UUID | None
    version: int | None
    attempts: tuple[dict[str, Any], ...]  # provider, model, result, seconds: never the text
    created_at: datetime
    finished_at: datetime | None
