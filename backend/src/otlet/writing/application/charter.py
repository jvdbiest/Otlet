# SPDX-License-Identifier: AGPL-3.0-or-later
"""The writing charter of a user (Joël, 2026-10-19): read, changed, put back to the default."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from otlet.writing.domain.charter import CHARTER_MAX, DEFAULT_CHARTER


class CharterStore(Protocol):
    def get(self, user_id: UUID) -> str | None: ...

    def set(self, user_id: UUID, charter: str | None) -> None: ...


class CharterError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Charter:
    text: str  # what drafts follow; empty: no charter
    is_default: bool


class Charters:
    def __init__(self, store: CharterStore) -> None:
        self._store = store

    def of(self, user_id: UUID) -> Charter:
        kept = self._store.get(user_id)
        return Charter(DEFAULT_CHARTER, True) if kept is None else Charter(kept, False)

    def set(self, user_id: UUID, text: str) -> Charter:
        text = text.strip()
        if len(text) > CHARTER_MAX:
            raise CharterError(f"{CHARTER_MAX} characters at most")
        self._store.set(user_id, text)
        return self.of(user_id)

    def reset(self, user_id: UUID) -> Charter:
        self._store.set(user_id, None)
        return self.of(user_id)
