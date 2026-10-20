# SPDX-License-Identifier: AGPL-3.0-or-later
"""The writing charter of a user (Joël, 2026-10-19): read, changed, put back to the default."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from otlet.writing.application.drafts import OUTPUT_TOKENS
from otlet.writing.domain.charter import CHARTER_MAX, DEFAULT_CHARTER
from otlet.writing.domain.draft import CHARS_PER_TOKEN, PROMPT_OVERHEAD_TOKENS


class CharterStore(Protocol):
    def get(self, user_id: UUID) -> str | None: ...

    def set(self, user_id: UUID, charter: str | None) -> None: ...


class CharterError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Charter:
    text: str  # what drafts follow; empty: no charter
    is_default: bool


@dataclass(frozen=True, slots=True)
class Room:
    """What a draft has room for in the window of the user's main model (Joël, 2026-10-19):
    the interface counts the charter as it is typed and shows what is left for the sources."""

    model: str | None  # the first model of the profile; None: unknown, the smallest window
    window_tokens: int
    rules_tokens: int  # the rules of Otlet, the brief and the tags around the sources
    answer_tokens: dict[str, int]  # by length of the article
    chars_per_token: int  # the estimate drafts use


class Charters:
    def __init__(
        self,
        store: CharterStore,
        window: Callable[[UUID], tuple[int, bool, str | None]] | None = None,
    ) -> None:
        """`window` gives the window of the user's main model, whether it is local, and its name."""
        self._store = store
        self._window = window

    def room(self, user_id: UUID) -> Room | None:
        if self._window is None:
            return None
        window, _, model = self._window(user_id)
        return Room(
            model,
            window,
            PROMPT_OVERHEAD_TOKENS,
            # As the drafts count it when they share the window out (source_budget).
            {length.value: tokens for length, tokens in OUTPUT_TOKENS.items()},
            CHARS_PER_TOKEN,
        )

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
