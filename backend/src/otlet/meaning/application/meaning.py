# SPDX-License-Identifier: AGPL-3.0-or-later
"""The items encoded in the background (ADR-0045, sens-1).

The job takes the items without a vector, the most recent first, and encodes them by small
batches until its time is spent: on the NAS, 322 ms per item, so the flow of a day (about
1,300 items) costs some seven minutes, and the items collected before take a few runs.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from otlet.meaning.domain.meaning import DIMENSIONS, MODEL, text_of

ENCODE_PENDING = "meaning.encode_pending"
BATCH = 32
# Seconds of encoding for one run of the job; the next run takes the rest.
TIME_BUDGET = 240.0


@dataclass(frozen=True, slots=True)
class Pending:
    workspace_id: UUID
    item_id: UUID
    title: str
    summary: str


class Encoder(Protocol):
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector of DIMENSIONS for each text, normalised, in order."""
        ...


class MeaningStore(Protocol):
    def pending(self, limit: int) -> list[Pending]:
        """Items without a vector, in every workspace, the most recent first."""
        ...

    def save(self, vectors: list[tuple[Pending, list[float]]], model: str) -> None: ...


class Meaning:
    def __init__(
        self,
        store: MeaningStore,
        encoder: Callable[[], Encoder],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        # Built on first need: the model takes some 700 MB, only while there is work.
        self._encoder = encoder
        self._clock = clock

    def encode_pending(self, budget: float = TIME_BUDGET) -> int:
        """Encodes items until none is left or the budget is spent; the number encoded."""
        started = self._clock()
        encoder: Encoder | None = None
        done = 0
        while self._clock() - started < budget:
            batch = self._store.pending(BATCH)
            if not batch:
                break
            encoder = encoder or self._encoder()
            vectors = encoder.encode([text_of(p.title, p.summary) for p in batch])
            if len(vectors) != len(batch) or any(len(v) != DIMENSIONS for v in vectors):
                raise ValueError("the encoder gave vectors of the wrong number or size")
            self._store.save(list(zip(batch, vectors, strict=True)), MODEL)
            done += len(batch)
        return done
