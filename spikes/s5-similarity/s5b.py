# SPDX-License-Identifier: AGPL-3.0-or-later
"""S5b: memory of potion loaded by model2vec with reduced weights (docs/spikes/S5b.md §3).

    python s5b.py float32|float16|int8 [--results results]

Same corpus, scores and calibration as s5.py, whose functions are reused unchanged.
Writes results/s5b-<variant>-<time>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

import s5

MODEL = "minishlab/potion-multilingual-128M"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=("float32", "float16", "int8"))
    parser.add_argument("--results", default=str(s5.HERE / "results"))
    args = parser.parse_args()

    result: dict[str, Any] = {
        "model": MODEL,
        "variant": args.variant,
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
        "cpus": os.cpu_count(),
    }

    # D1: memory
    before = s5.rss_mib()
    from model2vec import StaticModel

    started = time.perf_counter()
    model = StaticModel.from_pretrained(MODEL, quantize_to=args.variant, force_download=False)
    load_seconds = time.perf_counter() - started

    def embed(texts: list[str]) -> np.ndarray:
        return model.encode(list(texts), use_multiprocessing=False)

    embed(["Préchauffage du modèle.", "Warm-up of the model."])
    result["model_info"] = {"dim": model.dim, "dtype": str(model.embedding.dtype), "vocabulary": len(model.tokens)}

    # D4: throughput, same synthetic items as s5.py
    pairs = s5.load_pairs()
    pool = [s for p in pairs for s in s5.sentences(p["source"] + " " + p["derived"])]
    rng = random.Random(s5.SEED)
    passages = []
    for _ in range(2_000):
        item, size = [], 0
        while size < 5_000:
            sentence = rng.choice(pool)
            item.append(sentence)
            size += len(sentence) + 1
        passages += [" ".join(item[i : i + 3]) for i in range(0, len(item), 3)]
    started = time.perf_counter()
    cpu_started = time.process_time()
    for i in range(0, len(passages), 64):
        embed(passages[i : i + 64])
    result["throughput"] = {
        "items": 2_000,
        "passages": len(passages),
        "wall_seconds": round(time.perf_counter() - started, 1),
        "cpu_seconds": round(time.process_time() - cpu_started, 1),
    }
    after = s5.rss_mib()
    result["memory"] = {
        "rss_before_mib": round(before, 1),
        "rss_after_mib": round(after, 1),
        "model_mib": round(after - before, 1),
        "load_seconds": round(load_seconds, 1),
    }

    # D2, D3: scores and calibration, as in s5.py
    cache: dict[str, np.ndarray] = {}
    for pair in pairs:
        pair["semantic"] = s5.semantic_score(MODEL, embed, pair["source"], pair["derived"], cache)
        pair.update(s5.lexical_scores(pair["source"], pair["derived"]))
    calibration = {
        "semantic_same": s5.calibrate(pairs, "semantic", "same"),
        "semantic_cross": s5.calibrate(pairs, "semantic", "cross"),
    }
    thresholds = {k: v["threshold"] for k, v in calibration.items()}
    thresholds["ngram5_same"] = s5.LEXICAL_THRESHOLD
    for pair in pairs:
        pair["detected"] = s5.guard(pair, thresholds)

    def outcome(languages: str | None = None) -> dict[str, Any]:
        chosen = [p for p in pairs if p["half"] == "measure" and (languages is None or p["languages"] == languages)]
        positives = [p for p in chosen if p["positive"]]
        negatives = [p for p in chosen if not p["positive"]]
        return {
            "recall": round(sum(p["detected"] for p in positives) / len(positives), 4),
            "false_positive_rate": round(sum(p["detected"] for p in negatives) / len(negatives), 4),
            "positives": len(positives),
            "negatives": len(negatives),
        }

    result["calibration"] = calibration
    result["measure"] = {"all": outcome(), "same": outcome("same"), "cross": outcome("cross")}
    result["pairs"] = [
        {"topic": p["topic"], "category": p["category"], "semantic": round(p["semantic"], 4)} for p in pairs
    ]

    out = Path(args.results)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"s5b-{args.variant}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("variant", "model_info", "memory", "throughput")}, ensure_ascii=False))
    print(json.dumps({"thresholds": thresholds, "measure": result["measure"]["all"]}, ensure_ascii=False))
    print(f"Result: {path}")


if __name__ == "__main__":
    main()
