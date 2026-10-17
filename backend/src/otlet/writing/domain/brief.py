# SPDX-License-Identifier: AGPL-3.0-or-later
"""The brief: the instructions of an article, built on items the user kept (U03, F-RED-01).

Its author's angle and own contribution come first (M-19): it is what makes the article
theirs, and not one more rewriting of the sources. A brief on one source only is allowed and
said so: an article of news rests on two sources at least by default (FA, H5).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

TITLE_MAX_LENGTH = 200
ANGLE_MAX_LENGTH = 4000
FIELD_MAX_LENGTH = 200  # audience, tone, channel
MODEL_MAX_LENGTH = 200
ITEMS_MAX = 20
LANGUAGES = ("fr", "en", "de", "nl", "es", "it", "pt")
SOURCES_ADVISED = 2


class Length(StrEnum):
    SHORT = "short"  # about 300 words
    MEDIUM = "medium"  # about 600 words
    LONG = "long"  # about 1,200 words


class BriefError(Exception):
    """A rule of the brief was not met. `code` is stable and translated by the interface; the
    message explains it in English."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ModelChoice:
    """One provider of the author and one of its models; no choice means the author's profile."""

    provider_id: UUID
    model: str


@dataclass(frozen=True, slots=True)
class BriefFields:
    title: str
    item_ids: tuple[UUID, ...]
    angle: str = ""
    audience: str = ""
    tone: str = ""
    length: Length = Length.MEDIUM
    language: str = "fr"
    channel: str = ""
    model: ModelChoice | None = None

    def checked(self) -> "BriefFields":
        """The fields trimmed, or a BriefError naming the first rule they break."""
        title = self.title.strip()
        if not 1 <= len(title) <= TITLE_MAX_LENGTH:
            raise BriefError("invalid_title", f"a title has 1 to {TITLE_MAX_LENGTH} characters")
        angle = self.angle.strip()
        if len(angle) > ANGLE_MAX_LENGTH:
            raise BriefError("invalid_angle", f"an angle has at most {ANGLE_MAX_LENGTH} characters")
        short = {"audience": self.audience, "tone": self.tone, "channel": self.channel}
        for name, value in short.items():
            if len(value.strip()) > FIELD_MAX_LENGTH:
                raise BriefError(
                    f"invalid_{name}", f"{name} has at most {FIELD_MAX_LENGTH} characters"
                )
        if self.language not in LANGUAGES:
            raise BriefError("invalid_language", f"a language is one of {LANGUAGES}")
        items = tuple(dict.fromkeys(self.item_ids))
        if not 1 <= len(items) <= ITEMS_MAX:
            raise BriefError("invalid_items", f"a brief has 1 to {ITEMS_MAX} items")
        model = self.model
        if model is not None:
            name = model.model.strip()
            if not 1 <= len(name) <= MODEL_MAX_LENGTH:
                raise BriefError("invalid_model", "a model name is required with a provider")
            model = ModelChoice(model.provider_id, name)
        return BriefFields(
            title=title,
            item_ids=items,
            angle=angle,
            audience=self.audience.strip(),
            tone=self.tone.strip(),
            length=self.length,
            language=self.language,
            channel=self.channel.strip(),
            model=model,
        )


@dataclass(frozen=True, slots=True)
class BriefItem:
    """An item of a brief, as the brief shows it: enough to recognize it and open its page."""

    id: UUID
    title: str
    url: str | None
    source_id: UUID | None  # None for a manual entry
    source_name: str | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class Brief:
    id: UUID
    workspace_id: UUID
    created_by: UUID
    fields: BriefFields
    items: tuple[BriefItem, ...]
    created_at: datetime
    updated_at: datetime

    @property
    def sources(self) -> int:
        """How many sources the brief rests on: each manual entry counts as its own."""
        return len({item.source_id or item.id for item in self.items})

    @property
    def single_source(self) -> bool:
        return self.sources < SOURCES_ADVISED
