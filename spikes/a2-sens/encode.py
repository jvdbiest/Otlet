# SPDX-License-Identifier: AGPL-3.0-or-later
"""Spike ADR-0045: encode the items of the Veille with a small multilingual model, locally.

Reads items.jsonl (id, title, summary, language, dated), writes vectors.npy and ids.json next to
it, and prints the time per item and the memory of the process. No model provider, no network
after the model is downloaded once.

    python encode.py <folder> [model]
"""

import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SUMMARY_CHARS = 300


def text(item: dict) -> str:
    return f"{item['title']}. {(item.get('summary') or '')[:SUMMARY_CHARS]}"


def main() -> None:
    folder = Path(sys.argv[1])
    model_name = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL
    items = [json.loads(line) for line in (folder / "items.jsonl").open(encoding="utf-8")]
    started = time.perf_counter()
    model = TextEmbedding(model_name)
    loaded = time.perf_counter() - started
    started = time.perf_counter()
    vectors = np.array(list(model.embed([text(i) for i in items], batch_size=32)), dtype=np.float32)
    seconds = time.perf_counter() - started
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    tag = model_name.split("/")[-1]
    np.save(folder / f"vectors-{tag}.npy", vectors)
    (folder / "ids.json").write_text(json.dumps([i["id"] for i in items]))
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(
        json.dumps(
            {
                "model": model_name,
                "items": len(items),
                "dimensions": int(vectors.shape[1]),
                "load_seconds": round(loaded, 1),
                "encode_seconds": round(seconds, 1),
                "ms_per_item": round(1000 * seconds / len(items), 1),
                "peak_rss_mb": round(peak),
                "index_mb": round(vectors.nbytes / 1e6, 1),
            }
        )
    )


if __name__ == "__main__":
    main()
