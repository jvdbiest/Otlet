# SPDX-License-Identifier: AGPL-3.0-or-later
"""An image imported by a person (X03b, ADR-0036 §6): what Otlet keeps of it, and its limits."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# What a person may send: a photo from a phone fits, a poster scanned at 600 dpi does not.
MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 40_000_000  # decoded size: an image that unpacks to more is refused
# What Otlet keeps: no side longer than this, which covers a site's widest picture.
MAX_SIDE = 4096
FORMATS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class MediaError(ValueError):
    """An image refused, with a code the interface names: too_large, not_an_image."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Image:
    """An image as Otlet stores it: decoded, re-encoded without its metadata (GPS position,
    camera, author), turned upright, and no larger than MAX_SIDE."""

    data: bytes
    mime: str  # one of FORMATS
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Media:
    id: UUID
    sha256: str  # the address of its file
    mime: str
    width: int
    height: int
    size: int  # bytes
    created_at: datetime
