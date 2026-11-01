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

# The Reporter reads further (question of Joël on the cold, 2026-11-01). The articles that answer
# « Pourquoi risque-t-il de faire très froid ? » stood between 0.37 and 0.53, four of the five
# without the word « froid », and the floor kept one item of the whole Veille. Short items and
# questions sit lower than the spike's: the floor follows the best item. A best item under 0.55
# still means the Veille has nothing on it.
WIDE_TOP = 30
WIDE_BEST = 0.55
WIDE_MARGIN = 0.25
WIDE_FLOOR = 0.4


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


def widely_near[T](scored: Sequence[tuple[T, float]]) -> list[T]:
    """Of the items closest to a question, the closest first: those above NEAR_FLOOR, and among
    the first WIDE_TOP those not far under the best one."""
    if not scored or scored[0][1] < WIDE_BEST:
        return []
    floor = max(WIDE_FLOOR, scored[0][1] - WIDE_MARGIN)
    return [
        item
        for rank, (item, closeness) in enumerate(scored)
        if closeness >= NEAR_FLOOR or (rank < WIDE_TOP and closeness >= floor)
    ]
