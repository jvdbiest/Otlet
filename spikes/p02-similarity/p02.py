# SPDX-License-Identifier: AGPL-3.0-or-later
"""P02: the measure of docs/spikes/P02.md §3.

    python p02.py check <S5 corpus folder>   S5's CC0 corpus must give S5b's thresholds again
    python p02.py select <corpus folder>     the 50 sources, from the extract (no model)
    python p02.py score <corpus folder>      the groups, the scores, the verdict inputs
    python p02.py resources <one draft.json> <model>   C8, one pass: seconds and peak memory

Texts stay in the corpus folder, never versioned (ADR-0038); results hold ids and scores only.
"""

from __future__ import annotations

import glob
import hashlib
import json
import random
import re
import sys
import time
import unicodedata
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

SEED = 2026
HERE = Path(__file__).parent
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])")
WINDOW = 5
LEXICAL_THRESHOLD = 0.70
WIRE_SHARE = 0.05  # shared sequences of 8 words above which two articles are one wire story
NEAR_MIN = 0.5
NEAR_DAYS = 7
PER_LANGUAGE = {"fr": 26, "en": 14, "nl": 10}
PER_SOURCE = 4
MIN_WORDS, MAX_WORDS, MIN_SENTENCES = 250, 600, 8
PARTIAL_MIN = 6
POTION = "minishlab/potion-multilingual-128M"
MINILM = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# The same export as the product (backend/src/otlet/meaning/adapters/encoder.py).
MINILM_REPOSITORY = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
MINILM_REVISION = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
MODELS_DIR = Path("/models/p02")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE.split(text) if s.strip()]


def words(text: str) -> list[str]:
    return re.findall(r"[\w’']+", unicodedata.normalize("NFC", text.lower()))


def peak_mib() -> float:
    for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) / 1024
    return 0.0


# --- encoders ------------------------------------------------------------------------------


def potion() -> Any:
    from model2vec import StaticModel

    model = StaticModel.from_pretrained(POTION, quantize_to="int8", force_download=False)
    return lambda texts: model.encode(list(texts), use_multiprocessing=False)


def minilm() -> Any:
    import onnxruntime
    from tokenizers import Tokenizer

    folder = MODELS_DIR / "minilm"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("model_optimized.onnx", "tokenizer.json"):
        if not (folder / name).exists():
            url = f"https://huggingface.co/{MINILM_REPOSITORY}/resolve/{MINILM_REVISION}/{name}"
            urllib.request.urlretrieve(url, folder / name)  # noqa: S310 (a fixed https address)
    tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
    tokenizer.enable_truncation(256)
    tokenizer.enable_padding()
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = onnxruntime.InferenceSession(
        str(folder / "model_optimized.onnx"), options, providers=["CPUExecutionProvider"]
    )
    inputs = {i.name for i in session.get_inputs()}

    def embed(texts: list[str]) -> np.ndarray:
        out = []
        for start in range(0, len(texts), 8):
            encoded = tokenizer.encode_batch(list(texts[start : start + 8]))
            ids = np.array([e.ids for e in encoded], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            tokens = session.run(None, feed)[0]
            weights = mask[..., None].astype(np.float32)
            out.append((tokens * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1e-9))
        return np.concatenate(out)

    return embed


ENCODERS = {"potion": potion, "minilm": minilm}


class Scorer:
    def __init__(self, embed: Any) -> None:
        self._embed = embed
        self._cache: dict[str, np.ndarray] = {}

    def vectors(self, text: str) -> np.ndarray:
        if text not in self._cache:
            matrix = np.asarray(self._embed(sentences(text) or [text]), dtype=np.float32)
            norms = np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
            self._cache[text] = matrix / norms
        return self._cache[text]

    def scores(self, source: str, derived: str) -> tuple[float, float]:
        """The mean score (S5), and the highest mean over WINDOW consecutive sentences."""
        nearest = (self.vectors(derived) @ self.vectors(source).T).max(axis=1)
        if len(nearest) <= WINDOW:
            return float(nearest.mean()), float(nearest.mean())
        windows = np.convolve(nearest, np.ones(WINDOW) / WINDOW, mode="valid")
        return float(nearest.mean()), float(windows.max())


def lexical(source: str, derived: str) -> float:
    from rapidfuzz.distance import LCSseq

    s, d = words(source), words(derived)
    return LCSseq.similarity(s, d) / len(d) if d else 0.0


def wire_share(source: str, derived: str) -> float:
    s, d = words(source), words(derived)
    grams = {tuple(s[i : i + 8]) for i in range(len(s) - 7)}
    hits = [tuple(d[i : i + 8]) in grams for i in range(len(d) - 7)]
    return sum(hits) / len(hits) if hits else 0.0


# --- calibration and rates -----------------------------------------------------------------


def threshold_for(values: list[float]) -> float | None:
    """Highest threshold detecting at least 90 % of the positives (S5 §3.4)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[int(np.floor(0.10 * len(ordered)))]


def decided(pair: dict[str, Any], key: str, thresholds: dict[str, float | None]) -> bool:
    limit = thresholds[pair["languages"]]
    semantic = limit is not None and pair[key] >= limit
    if pair["languages"] == "cross":
        return semantic  # DR4: the semantic score alone
    return semantic or pair["lexical"] >= LEXICAL_THRESHOLD


def rate(pairs: list[dict[str, Any]], key: str, thresholds: dict[str, float | None]) -> dict[str, Any]:
    hits = sum(decided(p, key, thresholds) for p in pairs)
    return {"n": len(pairs), "detected": hits, "rate": round(hits / len(pairs), 4) if pairs else None}


def curve(pairs: list[dict[str, Any]], key: str, languages: str) -> list[dict[str, float | None]]:
    chosen = [p for p in pairs if p["languages"] == languages]
    positives = [p[key] for p in chosen if p["group"] in ("translation", "paraphrase")]
    negatives = [p[key] for p in chosen if p["group"].startswith("independent")]
    points = []
    for limit in np.round(np.arange(0.0, 1.0001, 0.02), 2):
        points.append(
            {
                "threshold": float(limit),
                "recall": round(sum(v >= limit for v in positives) / len(positives), 4) if positives else None,
                "fpr": round(sum(v >= limit for v in negatives) / len(negatives), 4) if negatives else None,
            }
        )
    return points


def evaluate(pairs: list[dict[str, Any]], drafts: list[dict[str, Any]], key: str) -> dict[str, Any]:
    calibration = [p for p in pairs if p["half"] == "calibration"]
    measure = [p for p in pairs if p["half"] == "measure"]
    thresholds = {
        languages: threshold_for(
            [p[key] for p in calibration if p["group"] in ("translation", "paraphrase") and p["languages"] == languages]
        )
        for languages in ("same", "cross")
    }

    def of(*groups: str) -> list[dict[str, Any]]:
        return [p for p in measure if p["group"] in groups]

    blocked = [d for d in drafts if any(decided(pair, key, thresholds) for pair in d["pairs"])]
    several = [d for d in drafts if d["sources"] >= 2]
    return {
        "thresholds": thresholds,
        "C1": rate(of("translation", "paraphrase"), key, thresholds),
        "C2": rate(of("translation"), key, thresholds),
        "paraphrases": rate(of("paraphrase"), key, thresholds),
        "C3": rate(of("independent_same", "independent_cross"), key, thresholds),
        "C3_same": rate(of("independent_same"), key, thresholds),
        "C3_cross": rate(of("independent_cross"), key, thresholds),
        "C4": {
            "versions": len(several),
            "blocked": sum(d in blocked for d in several),
            "rate": round(sum(d in blocked for d in several) / len(several), 4) if several else None,
            "articles": len({d["article"] for d in several}),
            "articles_blocked": len({d["article"] for d in several if d in blocked}),
        },
        "one_source": {
            "versions": sum(d["sources"] == 1 for d in drafts),
            "blocked": sum(d["sources"] == 1 and d in blocked for d in drafts),
        },
        "C7": rate(of("partial"), key, thresholds),
        "blocked_versions": [d["id"] for d in blocked],
        "curves": {languages: curve(pairs, key, languages) for languages in ("same", "cross")},
    }


# --- check: S5's own corpus ----------------------------------------------------------------


def check(corpus: str) -> None:
    pairs = []
    for path in sorted(glob.glob(f"{corpus}/topics-*.json")):
        for topic in json.loads(Path(path).read_text(encoding="utf-8")):
            for group in ("translation", "paraphrase"):
                pairs.append(
                    {
                        "calibration": topic["id"] % 2 == 1,
                        "languages": "cross" if group == "translation" else "same",
                        "source": topic["source"],
                        "derived": topic[group],
                    }
                )
    scorer = Scorer(potion())
    for pair in pairs:
        pair["mean"], pair["window"] = scorer.scores(pair["source"], pair["derived"])
    found = {
        languages: threshold_for([p["mean"] for p in pairs if p["calibration"] and p["languages"] == languages])
        for languages in ("same", "cross")
    }
    expected = {"same": 0.639, "cross": 0.548}
    good = all(abs((found[k] or 0.0) - expected[k]) <= 0.01 for k in expected)
    print(json.dumps({"found": found, "expected": expected, "good": good}))
    sys.exit(0 if good else 1)


# --- select: the 50 sources ----------------------------------------------------------------


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as lines:
        return [json.loads(line) for line in lines if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def usable(item: dict[str, Any]) -> bool:
    """An article of the sample or of the independents: full text, no duplicate, its vector."""
    return bool(item["sample"] and item["lang"] in PER_LANGUAGE and item["text"] and item["meaning"])


def select(corpus: Path) -> None:
    items = [i for i in read_jsonl(corpus / "candidates.jsonl") if usable(i)]
    items.sort(key=lambda i: i["id"])
    rng = random.Random(SEED)
    rng.shuffle(items)
    taken: Counter[str] = Counter()
    chosen: dict[str, list[dict[str, Any]]] = {lang: [] for lang in PER_LANGUAGE}
    for item in items:
        lang = item["lang"]
        size = len(item["text"].split())
        if (
            len(chosen[lang]) < PER_LANGUAGE[lang]
            and MIN_WORDS <= size <= MAX_WORDS
            and len(sentences(item["text"])) >= MIN_SENTENCES
            and taken[item["source_id"]] < PER_SOURCE
        ):
            chosen[lang].append(item)
            taken[item["source_id"]] += 1
    selected = []
    for lang, group in chosen.items():
        group.sort(key=lambda i: hashlib.sha256(i["id"].encode()).hexdigest())
        for index, item in enumerate(group):
            half = "calibration" if index % 2 == 0 else "measure"
            selected.append({"id": item["id"], "lang": lang, "half": half, "title": item["title"], "text": item["text"]})
    write_json(corpus / "selected.json", selected)
    print(json.dumps({"selected": Counter(s["lang"] for s in selected), "per_source_max": max(taken.values())}))


# --- the groups ----------------------------------------------------------------------------


def neighbour(
    item: dict[str, Any], vectors: dict[str, np.ndarray], items: list[dict[str, Any]], same: bool
) -> dict[str, Any] | None:
    """The nearest article by its stored vector: another source of the Veille, within NEAR_DAYS."""
    mine = vectors[item["id"]]
    day = datetime.fromisoformat(item["published_at"]) if item["published_at"] else None
    best, best_score = None, NEAR_MIN
    for other in items:
        if other["id"] == item["id"] or other["source_id"] == item["source_id"]:
            continue
        if (other["lang"] == item["lang"]) != same or not other["published_at"] or day is None:
            continue
        if abs((datetime.fromisoformat(other["published_at"]) - day).days) > NEAR_DAYS:
            continue
        score = float(mine @ vectors[other["id"]])
        if score >= best_score:
            best, best_score = other, score
    return best


def near_literal(text: str, rng: random.Random) -> str:
    """One sentence in five and one word in seven out (S5), and one word in ten replaced."""
    kept = [s for i, s in enumerate(sentences(text)) if i % 5 != 4]
    tokens = " ".join(kept).split()
    tokens = [t for i, t in enumerate(tokens) if i % 7 != 6]
    pool = list(tokens)
    return " ".join(rng.choice(pool) if i % 10 == 9 else t for i, t in enumerate(tokens))


def partial(derived: str, base: str) -> str | None:
    """A third of the final text taken from `derived`, in the middle of `base`."""
    copied = sentences(derived)
    around = sentences(base)
    size = max(PARTIAL_MIN, len(copied) // 3)
    if len(copied) < size or len(around) < 2:
        return None
    around = around[: size * 2]
    middle = len(around) // 2
    return " ".join([*around[:middle], *copied[:size], *around[middle:]])


def build_pairs(corpus: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    selected = json.loads((corpus / "selected.json").read_text(encoding="utf-8"))
    generated = {(g["id"], g["kind"]): g["text"] for g in read_jsonl(corpus / "generated.jsonl") if g["accepted"]}
    items = read_jsonl(corpus / "candidates.jsonl")
    items = [i for i in items if usable(i)]
    vectors = {i["id"]: np.asarray(json.loads(i["meaning"]), dtype=np.float32) for i in items}
    by_id = {i["id"]: i for i in items}
    rng = random.Random(SEED)
    pairs: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for chosen in selected:
        item = by_id[chosen["id"]]
        source = f"{item['title']}\n{item['text']}"

        def add(group: str, languages: str, derived: str, other: str | None = None) -> None:
            pairs.append(
                {
                    "group": group,
                    "languages": languages,
                    "half": chosen["half"],
                    "id": chosen["id"],
                    "other": other,
                    "source": source,
                    "derived": derived,
                }
            )

        translation = generated.get((chosen["id"], "translation"))
        paraphrase = generated.get((chosen["id"], "paraphrase"))
        if translation:
            add("translation", "cross", translation)
        if paraphrase:
            add("paraphrase", "same", paraphrase)
        add("near_literal", "same", near_literal(item["text"], rng))
        for same, group, languages in ((True, "independent_same", "same"), (False, "independent_cross", "cross")):
            near = neighbour(item, vectors, items, same)
            if near is None:
                counts[f"{group}_missing"] += 1
                continue
            if same and wire_share(source, f"{near['title']}\n{near['text']}") >= WIRE_SHARE:
                counts["wire_story"] += 1
                continue
            add(group, languages, f"{near['title']}\n{near['text']}", near["id"])
            copied = paraphrase if same else translation
            if copied:
                mixed = partial(copied, near["text"])
                if mixed:
                    add("partial", languages, mixed, near["id"])
                else:
                    counts["partial_skipped"] += 1
    counts.update(Counter(p["group"] for p in pairs))
    return pairs, dict(counts)


def build_drafts(corpus: Path) -> list[dict[str, Any]]:
    items = {i["id"]: i for i in read_jsonl(corpus / "candidates.jsonl")}
    drafts = []
    for draft in read_jsonl(corpus / "drafts.jsonl"):
        text = re.sub(r"\s*\[\d+(?:\s*,\s*\d+)*\]", "", f"{draft['title']}. {draft['body_text']}")
        sources = [items[i] for i in draft["item_ids"] if i in items and items[i]["text"]]
        if text.strip() and sources:
            drafts.append(
                {
                    "id": f"{draft['article_id']}:{draft['number']}",
                    "article": draft["article_id"],
                    "language": draft["language"],
                    "model": draft["model"],
                    "sources": len(sources),
                    "text": text,
                    "pairs": [
                        {
                            "item": s["id"],
                            # A source whose language is unknown is read as the draft's.
                            "languages": "cross" if s["lang"] not in (None, draft["language"]) else "same",
                            "source": f"{s['title']}\n{s['text']}",
                        }
                        for s in sources
                    ],
                }
            )
    return drafts


# --- score ---------------------------------------------------------------------------------


def deformations(corpus: Path, scorer: Scorer) -> list[dict[str, Any]]:
    """§3.6, information only: each sentence against the source sentence it distorts."""
    path = corpus / "deformations.jsonl"
    if not path.exists():
        return []
    found = []
    for row in read_jsonl(path):
        vectors = scorer.vectors(row["distorted"]) @ scorer.vectors(row["source"]).T
        found.append({"name": row["name"], "cosine": round(float(vectors.max()), 4)})
    return found


def score(corpus: Path, out: Path) -> None:
    if not (corpus / "review.ok").exists():
        sys.exit("review.ok is missing: read 5 translations and 5 paraphrases first (P02 §3.1)")
    pairs, counts = build_pairs(corpus)
    drafts = build_drafts(corpus)
    for pair in pairs:
        pair["lexical"] = lexical(pair["source"], pair["derived"])
    for draft in drafts:
        for pair in draft["pairs"]:
            pair["lexical"] = lexical(pair["source"], draft["text"])
    near = [p for p in pairs if p["group"] == "near_literal"]
    independents = [p for p in pairs if p["group"] == "independent_same"]
    result: dict[str, Any] = {
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
        "counts": counts,
        "drafts": len(drafts),
        "lexical_threshold": LEXICAL_THRESHOLD,
        "C5": {"n": len(near), "rate": round(sum(p["lexical"] >= LEXICAL_THRESHOLD for p in near) / len(near), 4)},
        "C6": {
            "n": len(independents),
            "rate": round(sum(p["lexical"] >= LEXICAL_THRESHOLD for p in independents) / len(independents), 4)
            if independents
            else None,
        },
        "lexical_means": {
            group: round(float(np.mean([p["lexical"] for p in pairs if p["group"] == group])), 4)
            for group in {p["group"] for p in pairs}
        },
        "models": {},
    }
    for name, encoder in ENCODERS.items():
        started = time.perf_counter()
        scorer = Scorer(encoder())
        for pair in pairs:
            pair["mean"], pair["window"] = scorer.scores(pair["source"], pair["derived"])
        for draft in drafts:
            for pair in draft["pairs"]:
                pair["mean"], pair["window"] = scorer.scores(pair["source"], draft["text"])
        result["models"][name] = {
            "seconds": round(time.perf_counter() - started, 1),
            "mean": evaluate(pairs, drafts, "mean"),
            "window": evaluate(pairs, drafts, "window"),
            "deformations": deformations(corpus, scorer),
            "pairs": [
                {
                    k: (round(p[k], 4) if isinstance(p[k], float) else p[k])
                    for k in ("group", "languages", "half", "id", "other", "lexical", "mean", "window")
                }
                for p in pairs
            ],
            "drafts": [
                {
                    "id": d["id"],
                    "sources": d["sources"],
                    "pairs": [
                        {k: (round(s[k], 4) if isinstance(s[k], float) else s[k]) for k in ("item", "languages", "lexical", "mean", "window")}
                        for s in d["pairs"]
                    ],
                }
                for d in drafts
            ],
        }
        if name == "potion":
            s5 = {"same": 0.640, "cross": 0.549}
            result["models"][name]["at_S5_thresholds"] = {
                "C1": rate([p for p in pairs if p["half"] == "measure" and p["group"] in ("translation", "paraphrase")], "mean", s5),
                "C3": rate([p for p in pairs if p["half"] == "measure" and p["group"].startswith("independent")], "mean", s5),
                "C4_blocked": sum(any(decided(s, "mean", s5) for s in d["pairs"]) for d in drafts if d["sources"] >= 2),
            }
        del scorer
    # C8 runs on the NAS with the longest draft of 5 sources; the file goes there and comes back.
    five = [d for d in drafts if d["sources"] == 5]
    if five:
        longest = max(five, key=lambda d: len(d["text"]))
        write_json(corpus / "c8.json", {"text": longest["text"], "sources": [s["source"] for s in longest["pairs"]]})
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"p02-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Result: {path}")


def resources(sample: str, name: str) -> None:
    draft = json.loads(Path(sample).read_text(encoding="utf-8"))
    started = time.perf_counter()
    scorer = Scorer(ENCODERS[name]())
    loaded = time.perf_counter() - started
    for source in draft["sources"]:
        scorer.scores(source, draft["text"])
    print(json.dumps({"model": name, "load_seconds": round(loaded, 1), "seconds": round(time.perf_counter() - started, 1), "peak_mib": round(peak_mib())}))


if __name__ == "__main__":
    command, *arguments = sys.argv[1:]
    if command == "check":
        check(arguments[0])
    elif command == "select":
        select(Path(arguments[0]))
    elif command == "score":
        score(Path(arguments[0]), HERE / "results")
    elif command == "resources":
        resources(arguments[0], arguments[1])
    else:
        sys.exit(__doc__)
