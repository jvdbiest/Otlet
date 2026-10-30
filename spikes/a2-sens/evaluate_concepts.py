# SPDX-License-Identifier: AGPL-3.0-or-later
"""Spike ADR-0045, sens-2: the meaning by question, or concept by concept?

The Reporter searches concepts, each with its terms, all of which an item must hold (budget AND
Bruxelles). The meaning can come in two ways:

- by question: the items closest to the question, added to the items the words find;
- by concept: an item holds a concept when it has one of its terms OR is among the K items
  closest to the concept; the items must hold every concept, as now.

The second keeps the restrictions (a place, an aspect) that the first ignores. The words of a
concept are matched here on title and summary by a simple rule, not by PostgreSQL: a stand-in
for the engine, the same for both ways.

    python evaluate_concepts.py <folder>
"""

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from evaluate import QUESTIONS, relevant  # noqa: E402

TOP = 30
RRF_K = 60


def folded(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def holds(text: str, terms: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(folded(t))}", text) for t in terms if t.strip())


def main() -> None:
    folder = Path(sys.argv[1])
    os.environ.setdefault("OTLET_MODELS_DIR", str(folder / "models"))
    import encoder_check as encoder  # the OnnxEncoder of otlet.meaning, copied next to this

    model = encoder.OnnxEncoder()
    items = [json.loads(line) for line in (folder / "items.jsonl").open(encoding="utf-8")]
    ids = json.loads((folder / "ids.json").read_text())
    vectors = np.load(folder / "vectors-paraphrase-multilingual-MiniLM-L12-v2.npy")
    texts = [folded(f"{i['title']} {i.get('summary') or ''}") for i in items]
    by_id = {i["id"]: n for n, i in enumerate(items)}
    asked = json.loads((folder / "lexical_in.json").read_text(encoding="utf-8"))
    lexical = json.loads((folder / "lexical.json").read_text())
    for key, (question, rules) in QUESTIONS.items():
        reference = {i["id"] for i in items if relevant(i, rules)}
        concepts = [terms for _, terms in asked[key]["concepts"]]
        q = np.array(model.encode([question])[0])
        closeness = vectors @ q
        print(f"\n### {question}  (référence : {len(reference)})")
        # By question (the spike): words of the engine, fused with the closest to the question.
        words = [i for i in lexical[key] if i in by_id]
        meaning = [ids[n] for n in np.argsort(-closeness)[: TOP * 3]]
        scores: dict[str, float] = {}
        for ranked in (words, meaning):
            for rank, item in enumerate(ranked):
                scores[item] = scores.get(item, 0) + 1 / (RRF_K + rank)
        by_question = sorted(scores, key=lambda i: -scores[i])[:TOP]
        hits = sum(i in reference for i in by_question)
        print(f"  par question        : {hits}/{len(reference)} trouvés, {hits}/{len(by_question)} justes")
        # By concept: words of the concept OR among the K closest to it, for every concept.
        concept_vectors = [np.array(v) for v in model.encode([" ; ".join(t[:8]) for t in concepts])]
        for k in (50, 100, 200):
            near = [set(np.argsort(-(vectors @ cv))[:k].tolist()) for cv in concept_vectors]
            kept = [
                n
                for n in range(len(items))
                if all(holds(texts[n], terms) or n in near[c] for c, terms in enumerate(concepts))
            ]
            ranked = [ids[n] for n in sorted(kept, key=lambda n: -closeness[n])][:TOP]
            hits = sum(i in reference for i in ranked)
            print(
                f"  par concept, K={k:<4}: {hits}/{len(reference)} trouvés, {hits}/{len(ranked)}"
                f" justes ({len(kept)} dans l'ensemble)"
            )
            if k == 100:
                for item in ranked[:6]:
                    mark = "+" if item in reference else " "
                    print(f"       {mark} {items[by_id[item]]['title'][:95]}")


if __name__ == "__main__":
    main()
