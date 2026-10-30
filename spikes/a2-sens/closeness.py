# SPDX-License-Identifier: AGPL-3.0-or-later
"""Spike ADR-0045, sens-2: how close is close? The cosine of the items closest to each question,
relevant or not, to choose the floor under which the meaning adds nothing.

    python closeness.py <folder>
"""

import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from evaluate import QUESTIONS, relevant  # noqa: E402

EXTRA = {
    "rien": "Les résultats du championnat de curling en Mongolie",
    "budget_federal": "Où en est le budget fédéral ?",
    "tesla": "Que se passe-t-il chez Tesla ?",
}


def main() -> None:
    folder = Path(sys.argv[1])
    os.environ.setdefault("OTLET_MODELS_DIR", str(folder / "models"))
    import encoder_check as encoder

    model = encoder.OnnxEncoder()
    items = [json.loads(line) for line in (folder / "items.jsonl").open(encoding="utf-8")]
    vectors = np.load(folder / "vectors-paraphrase-multilingual-MiniLM-L12-v2.npy")
    questions = {k: (q, rules) for k, (q, rules) in QUESTIONS.items()}
    questions |= {k: (q, None) for k, q in EXTRA.items()}
    for key, (question, rules) in questions.items():
        closeness = vectors @ np.array(model.encode([question])[0])
        order = np.argsort(-closeness)[:40]
        marks = "".join(
            "?" if rules is None else ("+" if relevant(items[n], rules) else ".") for n in order
        )
        print(f"{key:15} {closeness[order[0]]:.2f} {closeness[order[9]]:.2f} "
              f"{closeness[order[29]]:.2f}  {marks}")
        if rules is None:
            for n in order[:4]:
                print(f"     {closeness[n]:.2f} {items[n]['title'][:90]}")
        else:
            good = [closeness[n] for n in order if relevant(items[n], rules)]
            bad = [closeness[n] for n in order if not relevant(items[n], rules)]
            print(f"     justes {np.round(good[:8], 2)}  autres {np.round(bad[:8], 2)}")


if __name__ == "__main__":
    main()
