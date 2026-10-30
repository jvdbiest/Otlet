# SPDX-License-Identifier: AGPL-3.0-or-later
"""Spike ADR-0045: words alone, meaning alone, and both, on the questions that failed.

The reference of each question is a rule on title and summary written by hand from the bench
(all three languages); it is approximate, so the first titles of each method are printed too,
for a reading by eye. lexical.json holds the sets the Reporter's engine found with the terms the
model gave (bench of 2026-10-30).

    python evaluate.py <folder> [model]
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

TOP = 30
RRF_K = 60

QUESTIONS = {
    "hopitaux": (
        "La situation financière des hôpitaux en Flandre",
        [r"ziekenhui|hôpita|hospita", r"vlaa|flandre|flamand|flemish|vlaanderen",
         r"geld|winst|financ|déficit|tekort|pensioen|fusie|fusion|budget|besparing"],
    ),
    "budget_bxl": (
        "Le budget de la région Bruxelles-Capitale",
        [r"begroting|budget|financ|dette|schuld|belasting|fiscal|économi",
         r"brussel|bruxell", r"^(?!.*(fédéral|federale|wallonie-bruxelles|fwb)).*$"],
    ),
    "greves_sncb": (
        "Quoi de neuf sur les grèves à la SNCB ?",
        [r"sncb|nmbs|cheminot|ferroviai|spoor|rail|trein|train",
         r"grève|greve|staking|strike|préavis|syndica|vakbond|action"],
    ),
    "ia_ecole": (
        "Que dit-on de l'intelligence artificielle à l'école ?",
        [r"\bia\b|\bai\b|intelligence artificielle|kunstmatige|chatgpt|chatbot",
         r"école|school|élève|leerling|enseign|onderwijs|leraar|leraren|étudiant|student|classe|univers"],
    ),
    "train_espagne": (
        "Qui sont les victimes de l'accident de train en Espagne ?",
        [r"espagne|spanje|spain|espagnol|spaans|madrid|urda",
         r"train|trein|ferrovi|spoor|rail"],
    ),
    "motos": (
        "Les essais de motos récents",
        [r"^(essai|test|review|rijtest|getest)|l.essai|\bessai\b|\btest\b",
         r"moto|motorfiets|motorcycle|honda|yamaha|kawasaki|ducati|ktm|triumph|cfmoto|suzuki|"
         r"bmw r|scooter|trail|roadster|sportive"],
    ),
    "emploi": (
        "Les pertes d'emploi en Belgique",
        [r"pertes? d.emploi|licenci|emplois? (menacés|supprimés)|suppressions? d.emplois|"
         r"banen|ontslag|job cuts|layoff|jobs? (cut|lost)|faillite|faillissement|"
         r"restructur|herstructur|fermeture"],
    ),
}


def relevant(item: dict, rules: list[str]) -> bool:
    text = f"{item['title']} {item.get('summary') or ''}".lower()
    return all(re.search(rule, text) for rule in rules)


def main() -> None:
    folder = Path(sys.argv[1])
    model_name = sys.argv[2] if len(sys.argv) > 2 else (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    tag = model_name.split("/")[-1]
    items = [json.loads(line) for line in (folder / "items.jsonl").open(encoding="utf-8")]
    ids = json.loads((folder / "ids.json").read_text())
    vectors = np.load(folder / f"vectors-{tag}.npy")
    lexical = json.loads((folder / "lexical.json").read_text())
    by_id = {i["id"]: i for i in items}
    from fastembed import TextEmbedding  # the spike's encoder

    model = TextEmbedding(model_name)
    summary = {}
    for key, (question, rules) in QUESTIONS.items():
        reference = {i["id"] for i in items if relevant(i, rules)}
        query = next(iter(model.embed([question])))
        query = query / np.linalg.norm(query)
        order = np.argsort(-(vectors @ query))
        meaning = [ids[n] for n in order[: TOP * 3]]
        words = [i for i in lexical[key] if i in by_id]
        scores: dict[str, float] = {}
        for rank, item in enumerate(words):
            scores[item] = scores.get(item, 0) + 1 / (RRF_K + rank)
        for rank, item in enumerate(meaning):
            scores[item] = scores.get(item, 0) + 1 / (RRF_K + rank)
        both = sorted(scores, key=lambda i: -scores[i])
        result = {}
        for name, ranked in (("mots", words), ("sens", meaning), ("hybride", both)):
            top = ranked[:TOP]
            hits = [i for i in top if i in reference]
            result[name] = {
                "trouvés": f"{len(hits)}/{len(reference)}",
                "justes_dans_top": f"{len(hits)}/{len(top)}",
            }
        summary[key] = result
        print(f"\n### {question}  (référence : {len(reference)})")
        for name, ranked in (("mots", words), ("sens", meaning), ("hybride", both)):
            print(f"  {name:8} {result[name]}")
            for item in ranked[:8]:
                mark = "+" if item in reference else " "
                print(f"     {mark} {by_id[item]['title'][:100]}")
    print("\n" + json.dumps({"model": model_name, "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
