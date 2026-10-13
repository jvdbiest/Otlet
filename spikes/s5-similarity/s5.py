# SPDX-License-Identifier: AGPL-3.0-or-later
"""S5: the whole measure of docs/spikes/S5.md §3, one command per model.

    python s5.py <model name> [--results results]

1. C1, C2: loads the model with fastembed in this process (RSS before and after), then
   vectorizes 2 000 synthetic items of about 5 KB split into passages of 2 to 3 sentences,
   timed. Run in a container limited to 2 vCPU.
2. C3, C4, C5: scores the 200 pairs of the corpus (semantic, and lexical for same-language
   pairs), calibrates thresholds on the odd topics, applies them unchanged to the even topics.
Writes results/s5-<model slug>-<time>.json.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
import resource
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).parent
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])")
CATEGORIES = ("translation", "paraphrase", "independent_same", "independent_other")
SEED = 2026
LEXICAL_THRESHOLD = 0.5  # fixed by principle, docs/spikes/S5.md §3.2


def rss_mib() -> float:
    with open("/proc/self/status", encoding="ascii") as status:
        for line in status:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE.split(text) if s.strip()]


def load_pairs() -> list[dict[str, Any]]:
    pairs = []
    for path in sorted(glob.glob(str(HERE / "corpus" / "topics-*.json"))):
        for topic in json.loads(Path(path).read_text(encoding="utf-8")):
            other = "en" if topic["lang"] == "fr" else "fr"
            for category in CATEGORIES:
                cross = category in ("translation", "independent_other")
                pairs.append(
                    {
                        "topic": topic["id"],
                        "half": "calibration" if topic["id"] % 2 else "measure",
                        "category": category,
                        "positive": category in ("translation", "paraphrase"),
                        "languages": "cross" if cross else "same",
                        "source_lang": topic["lang"],
                        "derived_lang": other if cross else topic["lang"],
                        "source": topic["source"],
                        "derived": topic[category],
                    }
                )
    return pairs


# --- lexical -------------------------------------------------------------------------------

def words(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.lower())
    return re.findall(r"[\w’']+", text)


def ngrams(tokens: list[str], n: int = 5) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def lexical_scores(source: str, derived: str) -> dict[str, float]:
    from datasketch import MinHash
    from rapidfuzz.distance import LCSseq

    s, d = words(source), words(derived)
    ds, ss = ngrams(d), ngrams(s)
    overlap = len(ds & ss) / len(ds) if ds else 0.0
    m1, m2 = MinHash(num_perm=128, seed=1), MinHash(num_perm=128, seed=1)
    for gram in ss:
        m1.update(" ".join(gram).encode())
    for gram in ds:
        m2.update(" ".join(gram).encode())
    lcs = LCSseq.similarity(s, d) / len(d) if d else 0.0
    return {"ngram5": overlap, "minhash": m1.jaccard(m2), "lcs": lcs}


# --- semantic ------------------------------------------------------------------------------

def prefixed(model: str, texts: list[str]) -> list[str]:
    return [f"query: {t}" for t in texts] if "e5" in model.lower() else texts


def semantic_score(model_name: str, embed, source: str, derived: str, cache: dict[str, np.ndarray]) -> float:
    def vectors(text: str) -> np.ndarray:
        if text not in cache:
            parts = sentences(text)
            matrix = np.array(list(embed(prefixed(model_name, parts))))
            cache[text] = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
        return cache[text]

    s, d = vectors(source), vectors(derived)
    return float((d @ s.T).max(axis=1).mean())


# --- calibration ---------------------------------------------------------------------------

def calibrate(pairs: list[dict[str, Any]], key: str, languages: str) -> dict[str, Any]:
    """Highest threshold detecting >= 90 % of the positives of the calibration half."""
    cal = [p for p in pairs if p["half"] == "calibration" and p["languages"] == languages]
    positives = sorted(p[key] for p in cal if p["positive"])
    index = int(np.floor(0.10 * len(positives)))
    threshold = positives[index] if positives else 1.0
    return {"threshold": round(threshold, 4), **rates(cal, key, threshold)}


def rates(pairs: list[dict[str, Any]], key: str, threshold: float) -> dict[str, Any]:
    positives = [p for p in pairs if p["positive"]]
    negatives = [p for p in pairs if not p["positive"]]
    detected = sum(p[key] >= threshold for p in positives)
    false = sum(p[key] >= threshold for p in negatives)
    return {
        "recall": round(detected / len(positives), 4) if positives else None,
        "false_positive_rate": round(false / len(negatives), 4) if negatives else None,
        "positives": len(positives),
        "negatives": len(negatives),
    }


def curve(pairs: list[dict[str, Any]], key: str, languages: str) -> list[dict[str, float]]:
    chosen = [p for p in pairs if p["languages"] == languages]
    points = []
    for threshold in np.round(np.arange(0.0, 1.0001, 0.02), 2):
        r = rates(chosen, key, float(threshold))
        points.append({"threshold": float(threshold), "recall": r["recall"], "fpr": r["false_positive_rate"]})
    return points


def guard(pair: dict[str, Any], thresholds: dict[str, float]) -> bool:
    """docs/spikes/S5.md §3.2: same language = lexical OR semantic; cross = semantic only."""
    if pair["languages"] == "cross":
        return pair["semantic"] >= thresholds["semantic_cross"]
    return pair["semantic"] >= thresholds["semantic_same"] or pair["ngram5"] >= thresholds["ngram5_same"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--results", default=str(HERE / "results"))
    args = parser.parse_args()

    from fastembed import TextEmbedding

    supported = {m["model"] for m in TextEmbedding.list_supported_models()}
    if args.model == "intfloat/multilingual-e5-small" and args.model not in supported:
        # Not in fastembed's list (0.9.0): declared from its official ONNX export.
        from fastembed.common.model_description import ModelSource, PoolingType

        TextEmbedding.add_custom_model(
            model=args.model,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf=args.model),
            dim=384,
            model_file="onnx/model.onnx",
            license="mit",
            size_in_gb=0.47,
        )

    result: dict[str, Any] = {"model": args.model, "started": datetime.now(UTC).isoformat(timespec="seconds"), "cpus": os.cpu_count()}

    # C1: memory
    before = rss_mib()
    started = time.perf_counter()
    model = TextEmbedding(model_name=args.model, threads=2)
    load_seconds = time.perf_counter() - started
    list(model.embed(["Préchauffage du modèle.", "Warm-up of the model."]))
    description = next((m for m in TextEmbedding.list_supported_models() if m["model"] == args.model), {})
    result["model_info"] = {k: description.get(k) for k in ("dim", "license", "size_in_GB", "sources")}

    # C2: throughput on 2 000 synthetic items of about 5 KB
    pairs = load_pairs()
    pool = [s for p in pairs for s in sentences(p["source"] + " " + p["derived"])]
    rng = random.Random(SEED)
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
    for _ in model.embed(prefixed(args.model, passages), batch_size=64):
        pass
    result["throughput"] = {
        "items": 2_000,
        "passages": len(passages),
        "wall_seconds": round(time.perf_counter() - started, 1),
        "cpu_seconds": round(time.process_time() - cpu_started, 1),
    }
    result["memory"] = {"rss_before_mib": round(before, 1), "rss_after_mib": round(rss_mib(), 1), "model_mib": round(rss_mib() - before, 1), "load_seconds": round(load_seconds, 1)}

    # C3, C4, C5: scores
    cache: dict[str, np.ndarray] = {}
    for pair in pairs:
        pair["semantic"] = semantic_score(args.model, model.embed, pair["source"], pair["derived"], cache)
        pair.update(lexical_scores(pair["source"], pair["derived"]))

    calibration = {
        "semantic_same": calibrate(pairs, "semantic", "same"),
        "semantic_cross": calibrate(pairs, "semantic", "cross"),
    }
    thresholds = {k: v["threshold"] for k, v in calibration.items()}
    thresholds["ngram5_same"] = LEXICAL_THRESHOLD
    for pair in pairs:
        pair["detected"] = guard(pair, thresholds)

    def outcome(half: str, languages: str | None = None) -> dict[str, Any]:
        chosen = [p for p in pairs if p["half"] == half and (languages is None or p["languages"] == languages)]
        positives = [p for p in chosen if p["positive"]]
        negatives = [p for p in chosen if not p["positive"]]
        return {
            "recall": round(sum(p["detected"] for p in positives) / len(positives), 4),
            "false_positive_rate": round(sum(p["detected"] for p in negatives) / len(negatives), 4),
            "positives": len(positives),
            "negatives": len(negatives),
            "by_category": {
                c: round(sum(p["detected"] for p in chosen if p["category"] == c) / max(1, sum(1 for p in chosen if p["category"] == c)), 4)
                for c in CATEGORIES
            },
        }

    result["calibration"] = calibration
    result["measure"] = {"all": outcome("measure"), "same": outcome("measure", "same"), "cross": outcome("measure", "cross")}
    result["whole_corpus_information"] = {
        "same": rates([p for p in pairs if p["languages"] == "same"], "semantic", thresholds["semantic_same"]),
        "cross": rates([p for p in pairs if p["languages"] == "cross"], "semantic", thresholds["semantic_cross"]),
    }
    # S5.4: lexical part alone, on paraphrases and on 50 automatic quasi-literal copies.
    literal = []
    for topic_pairs in {p["topic"]: p for p in pairs if p["category"] == "paraphrase"}.values():
        kept = [s for i, s in enumerate(sentences(topic_pairs["source"])) if (i + 1) % 5]
        tokens = " ".join(kept).split()
        copy = " ".join(t for i, t in enumerate(tokens) if (i + 1) % 7)
        scores = lexical_scores(topic_pairs["source"], copy)
        scores["semantic"] = semantic_score(args.model, model.embed, topic_pairs["source"], copy, cache)
        literal.append(scores)
    paraphrases = [p for p in pairs if p["category"] == "paraphrase"]
    independents = [p for p in pairs if p["category"] == "independent_same"]
    result["lexical_part"] = {
        "threshold_ngram5": LEXICAL_THRESHOLD,
        "quasi_literal_detected": round(sum(s["ngram5"] >= LEXICAL_THRESHOLD for s in literal) / len(literal), 4),
        "paraphrases_detected": round(sum(p["ngram5"] >= LEXICAL_THRESHOLD for p in paraphrases) / len(paraphrases), 4),
        "independents_flagged": round(sum(p["ngram5"] >= LEXICAL_THRESHOLD for p in independents) / len(independents), 4),
        "mean_scores": {
            group: {k: round(float(np.mean([x[k] for x in items])), 4) for k in ("ngram5", "minhash", "lcs", "semantic")}
            for group, items in (("quasi_literal", literal), ("paraphrase", paraphrases), ("independent_same", independents))
        },
    }
    result["curves"] = {
        "semantic_same": curve(pairs, "semantic", "same"),
        "semantic_cross": curve(pairs, "semantic", "cross"),
    }
    result["pairs"] = [
        {k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items() if k not in ("source", "derived")}
        for p in pairs
    ]

    out = Path(args.results)
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", args.model.lower()).strip("-")
    path = out / f"s5-{slug}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("model", "memory", "throughput")}, ensure_ascii=False))
    print(json.dumps({"thresholds": thresholds, "measure": result["measure"]["all"]}, ensure_ascii=False))
    print(f"Result: {path}")


if __name__ == "__main__":
    main()
