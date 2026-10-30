# SPDX-License-Identifier: AGPL-3.0-or-later
"""The items of the words and the items of the meaning, ranked together (ADR-0045).

Spike of 2026-10-30: the 60 items closest to the question, if at least 0.6 close (the relevant
items of the benches were above, a question on nothing of the Veille stayed below 0.55), fused
with the items of the words by reciprocal rank.
"""

from collections.abc import Callable, Hashable, Sequence

NEAR_MAX = 60
NEAR_FLOOR = 0.6
RRF_K = 60


def fused[T](rankings: Sequence[Sequence[T]], key: Callable[[T], Hashable], limit: int) -> list[T]:
    """The items of every ranking, by the sum of 1 / (RRF_K + rank); the first seen kept."""
    scores: dict[Hashable, float] = {}
    first: dict[Hashable, T] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            k = key(item)
            scores[k] = scores.get(k, 0.0) + 1 / (RRF_K + rank)
            first.setdefault(k, item)
    return [first[k] for k in sorted(scores, key=lambda k: -scores[k])][:limit]
