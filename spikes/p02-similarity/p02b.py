# SPDX-License-Identifier: AGPL-3.0-or-later
"""P02b: the measure of docs/spikes/P02b.md §3, with the functions of p02.py.

    python p02b.py select <P02 folder> <P02b folder>   the fresh sources (no model)
    python p02b.py score <P02 folder> <P02b folder>    the groups and the criteria
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

import p02

THRESHOLDS: dict[str, float | None] = {"same": 0.85, "cross": 0.80}
NEGATIVES_MAX = 100
NEGATIVES_READ = 400


def select(first: Path, second: Path) -> None:
    """P02's sources are out of the candidates; p02.select then applies the same rules."""
    seen = {s["id"] for s in json.loads((first / "selected.json").read_text(encoding="utf-8"))}
    with (second / "candidates.jsonl").open("w", encoding="utf-8") as out:
        for item in p02.read_jsonl(first / "candidates.jsonl"):
            if item["id"] not in seen:
                out.write(json.dumps(item, ensure_ascii=False) + "\n")
    p02.select(second)


def more_negatives(second: Path, pairs: list[dict[str, Any]]) -> dict[str, int]:
    """Independent pairs from other articles of the candidates, up to NEGATIVES_MAX per group."""
    items = p02.distinct(p02.read_jsonl(second / "candidates.jsonl"))
    vectors = {i["id"]: np.asarray(json.loads(i["meaning"]), dtype=np.float32) for i in items}
    chosen = {s["id"] for s in json.loads((second / "selected.json").read_text(encoding="utf-8"))}
    known = {frozenset((p["id"], p["other"])) for p in pairs if p["other"]}
    count = {g: sum(p["group"] == g for p in pairs) for g in ("independent_same", "independent_cross")}
    pool = [i for i in items if i["id"] not in chosen and i["published_at"]]
    random.Random(p02.SEED).shuffle(pool)
    read = wires = 0
    for item in pool[:NEGATIVES_READ]:
        if all(n >= NEGATIVES_MAX for n in count.values()):
            break
        read += 1
        source = f"{item['title']}\n{item['text']}"
        for same, group, languages in ((True, "independent_same", "same"), (False, "independent_cross", "cross")):
            if count[group] >= NEGATIVES_MAX:
                continue
            near = p02.neighbour(item, vectors, items, same)
            if near is None or frozenset((item["id"], near["id"])) in known:
                continue
            derived = f"{near['title']}\n{near['text']}"
            if same and p02.wire_share(source, derived) >= p02.WIRE_SHARE:
                wires += 1
                continue
            known.add(frozenset((item["id"], near["id"])))
            count[group] += 1
            pairs.append(
                {"group": group, "languages": languages, "half": "measure", "id": item["id"], "other": near["id"], "source": source, "derived": derived}
            )
    return {"negatives_read": read, "negatives_wire": wires}


def score(first: Path, second: Path, out: Path) -> None:
    if not (second / "review.ok").exists():
        sys.exit("review.ok is missing: read 5 translations and 5 paraphrases first (P02b §3)")
    pairs, counts = p02.build_pairs(second)
    counts.update(more_negatives(second, pairs))
    drafts = p02.build_drafts(first)
    for pair in pairs:
        pair["lexical"] = p02.lexical(pair["source"], pair["derived"])
    for draft in drafts:
        for pair in draft["pairs"]:
            pair["lexical"] = p02.lexical(pair["source"], draft["text"])
    started = time.perf_counter()
    scorer = p02.Scorer(p02.minilm())
    for pair in pairs:
        pair["mean"], pair["window"] = scorer.scores(pair["source"], pair["derived"])
    for draft in drafts:
        for pair in draft["pairs"]:
            pair["mean"], pair["window"] = scorer.scores(pair["source"], draft["text"])

    def of(*groups: str) -> list[dict[str, Any]]:
        return [p for p in pairs if p["group"] in groups]

    def rate(group: list[dict[str, Any]]) -> dict[str, Any]:
        return p02.rate(group, "window", THRESHOLDS)

    near, same = of("near_literal"), of("independent_same")
    several = [d for d in drafts if d["sources"] >= 2]
    blocked = [d for d in drafts if any(p02.decided(s, "window", THRESHOLDS) for s in d["pairs"])]
    result = {
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(time.perf_counter() - started, 1),
        "thresholds": THRESHOLDS,
        "counts": counts,
        "C1": rate(of("translation", "paraphrase")),
        "C2": rate(of("translation")),
        "paraphrases": rate(of("paraphrase")),
        "C3_same": rate(of("independent_same")),
        "C3_cross": rate(of("independent_cross")),
        "C4": {
            "versions": len(several),
            "blocked": sum(d in blocked for d in several),
            "rate": round(sum(d in blocked for d in several) / len(several), 4),
            "articles": len({d["article"] for d in several}),
            "articles_blocked": len({d["article"] for d in several if d in blocked}),
        },
        "one_source": {"versions": sum(d["sources"] == 1 for d in drafts), "blocked": sum(d["sources"] == 1 and d in blocked for d in drafts)},
        "C5": {"n": len(near), "rate": round(sum(p["lexical"] >= p02.LEXICAL_THRESHOLD for p in near) / len(near), 4)},
        "C6": {"n": len(same), "rate": round(sum(p["lexical"] >= p02.LEXICAL_THRESHOLD for p in same) / len(same), 4) if same else None},
        "C7": rate(of("partial")),
        "blocked_versions": [d["id"] for d in blocked],
        "pairs": [
            {k: (round(p[k], 4) if isinstance(p[k], float) else p[k]) for k in ("group", "languages", "id", "other", "lexical", "mean", "window")}
            for p in pairs
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"p02b-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Result: {path}")


if __name__ == "__main__":
    command, first_folder, second_folder = sys.argv[1:]
    if command == "select":
        select(Path(first_folder), Path(second_folder))
    elif command == "score":
        score(Path(first_folder), Path(second_folder), p02.HERE / "results")
    else:
        sys.exit(__doc__)
