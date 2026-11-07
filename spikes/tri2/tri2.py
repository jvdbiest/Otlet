# SPDX-License-Identifier: AGPL-3.0-or-later
"""TRI2: docs/spikes/TRI2.md §3. Can the sort tell « answers the question » from « same theme »?
Three variants on the frozen sets of TRI1, through the gateway of the product and the author's
own model, one call at a time, two passes each.

Run in the worker container (run-tri2.sh):  python tri2.py <folder> [--pilot]
Read anywhere, standard library only:       python3 tri2.py <folder> --summary

<folder> holds items.jsonl and labels.csv of TRI1, and receives calls.jsonl. Finished calls are
skipped, so a stopped run resumes.
"""

import csv
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

USER = "1fd3f00a-87b4-4473-aaf9-db737556c1b8"
OUTPUT_TOKENS = 8192
MAX_SECONDS = 3 * 3600
REFERENCE = ("Pourquoi risque", "Quelles sont", "Les essais")  # froid, Ukraine, motos
CONTROLS = ("La situation", "Que rachète", "Les pertes", "Les prix")
PASSES = (1, 2)
BATCH = {"B": 25, "E": 8}
EVIDENCE_BATCH = 10
EVIDENCE_MIN_WORDS = 5
SUMMARY_SENT = 300  # as the product sends it (qualify.py)

EVIDENCE_SYSTEM = (
    "Tu aides un auteur à choisir, dans sa veille de presse, les articles qui l'aident à "
    "répondre à sa question. Pour chaque élément (titre et début de résumé, dans sa langue "
    "d'origine), réponds « repond » vrai seulement si le titre ou le résumé contient un passage "
    "qui répond, au moins en partie, à la question, et recopie ce passage mot pour mot dans "
    "« preuve », sans rien y changer. Si l'élément porte seulement sur le même thème, ou ne "
    "mentionne le sujet qu'en passant, réponds « repond » faux et laisse « preuve » vide. "
    "Ne déduis rien que l'élément n'écrit pas. Réponds pour chaque numéro reçu, et seulement "
    "pour eux."
)
EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "repond": {"type": "boolean"},
                    "preuve": {"type": "string"},
                },
                "required": ["n", "repond", "preuve"],
            },
        }
    },
    "required": ["verdicts"],
}

# Thresholds of §2, fixed before any measure.
RECALL_MIN = 0.85
REJECTED_MAX = 0.03
PRECISION_MIN = 0.85
PRECISION_EACH_MIN = 0.75
STABILITY_MIN = 0.80
CONTROL_RECALL_DROP_MAX = 0.05
COST_MAX = 2.5


def fold(text: str) -> str:
    bare = unicodedata.normalize("NFKD", text.casefold().replace("’", "'"))
    bare = "".join(c for c in bare if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", bare))


def evidence_holds(proof: str, item: dict) -> bool:
    """The proof is a passage of what the model was sent, of EVIDENCE_MIN_WORDS words at least."""
    words = fold(proof)
    sent = fold(f"{item['title']} {item['summary'][:SUMMARY_SENT]}")
    return len(words.split()) >= EVIDENCE_MIN_WORDS and words in sent


def load(folder: Path) -> dict[str, list[dict]]:
    labels = {
        (row["question"], int(row["rank"])): row
        for row in csv.DictReader((folder / "labels.csv").open(encoding="utf-8"))
    }
    sets: dict[str, list[dict]] = {}
    for line in (folder / "items.jsonl").open(encoding="utf-8"):
        item = json.loads(line)
        key = next((k for k in (*REFERENCE, *CONTROLS) if item["question"].startswith(k)), None)
        if key is None or not item["summary"].strip():
            continue  # without a summary, the product sets « à vérifier » without a model
        label = labels[(key, item["rank"])]
        assert label["id"] == item["id"]
        sets.setdefault(key, []).append({**item, "label": label["label"]})
    return sets


def calls(folder: Path) -> list[dict]:
    path = folder / "calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def verdicts(made: list[dict], variant: str, run: int) -> dict[tuple[str, str], str]:
    """The final verdict of each item, for a variant and a pass. D: B, then the evidence stage
    on what B kept."""
    first = "B" if variant == "D" else variant
    out = {
        (c["key"], item): v[0]
        for c in made
        if c["variant"] == first and c["pass"] == run
        for item, v in c["verdicts"].items()
    }
    if variant == "D":
        for c in made:
            if c["variant"] == "D" and c["pass"] == run:
                out.update({(c["key"], item): v[0] for item, v in c["verdicts"].items()})
    return out


def plan(sets: dict[str, list[dict]], made: list[dict]) -> list[tuple]:
    """The calls still to make, in order: each pass of the reference, then the controls."""
    todo: list[tuple] = []
    for keys, runs in ((REFERENCE, PASSES), (CONTROLS, (1,))):
        for run in runs:
            for variant in ("B", "D", "E"):
                for key in keys:
                    items = sets[key]
                    if variant == "D":
                        kept = verdicts(made, "B", run)
                        if not any(c["variant"] == "B" and c["pass"] == run and c["key"] == key
                                   for c in made):
                            continue  # B of this pass first
                        items = [i for i in items if kept.get((key, i["id"])) == "traite"]
                        size = EVIDENCE_BATCH
                    else:
                        size = BATCH[variant]
                    for start in range(0, len(items), size):
                        todo.append((variant, run, key, start, items[start : start + size]))
    done = {(c["variant"], c["pass"], c["key"], c["start"]) for c in made}
    return [t for t in todo if t[:4] not in done]


def run(folder: Path, pilot: bool) -> None:
    from uuid import UUID

    from otlet.ai.adapters.jobs import gateway
    from otlet.assistant.adapters.ai_model import GatewayModel
    from otlet.assistant.domain.qualify import (
        QUALIFY_SCHEMA,
        QUALIFY_SYSTEM,
        Line,
        check_qualify,
        qualify_message,
        read_qualify,
    )
    from otlet.assistant.domain.terms import publisher_country
    from otlet.jobs.application.registry import JobEnvironment
    from otlet.platform import database
    from otlet.platform.config import Settings

    settings = Settings.from_env()
    env = JobEnvironment(
        database.create_engine(settings.require_database_url()),
        secrets_private_key_file=settings.secrets_private_key_file,
    )
    model = GatewayModel(gateway(env), "reporter", cancelled=lambda: False)
    sets = load(folder)
    started = time.monotonic()
    while True:
        todo = plan(sets, calls(folder))
        if not todo:
            print("complete", flush=True)
            return
        if time.monotonic() - started > MAX_SECONDS:
            print("max duration reached", flush=True)
            return
        variant, run_number, key, start, batch = todo[0]
        question = batch[0]["question"]
        lines = [
            Line(i["title"], i["summary"], i["language"], i["publisher"], publisher_country(i["url"]))
            for i in batch
        ]
        message = qualify_message(question, "", lines)
        began = time.monotonic()
        if variant == "D":
            asked = model.ask(
                UUID(USER), EVIDENCE_SYSTEM, message, EVIDENCE_SCHEMA, check_evidence, OUTPUT_TOKENS
            )
            judged = read_evidence(asked.text, batch) if asked.text else {}
        else:
            asked = model.ask(
                UUID(USER), QUALIFY_SYSTEM, message, QUALIFY_SCHEMA, check_qualify, OUTPUT_TOKENS
            )
            read = read_qualify(asked.text, len(batch)) if asked.text else {}
            judged = {batch[n - 1]["id"]: [j.verdict.value, j.reason] for n, j in read.items()}
        record = {
            "variant": variant, "pass": run_number, "key": key, "start": start,
            "seconds": round(time.monotonic() - began, 1), "error": asked.error, "verdicts": judged,
        }
        with (folder / "calls.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(variant, run_number, key, start, record["seconds"], len(judged), flush=True)
        if pilot:
            return
        time.sleep(5)


def check_evidence(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        return [f"not JSON: {error.msg}"]
    if not isinstance(data, dict) or not isinstance(data.get("verdicts"), list):
        return ["verdicts: a list is required"]
    return []


def read_evidence(raw: str, batch: list[dict]) -> dict[str, list[str]]:
    """« traite » when the model says it answers and quotes a passage that the item holds; else
    « proche ». An item without an answer stays « proche » too: it was only « traite » for B."""
    out = {i["id"]: ["proche", "sans réponse"] for i in batch}
    for entry in json.loads(raw)["verdicts"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("n"), int):
            continue
        if not 1 <= entry["n"] <= len(batch):
            continue
        item = batch[entry["n"] - 1]
        proof = str(entry.get("preuve", ""))
        if entry.get("repond") is True and evidence_holds(proof, item):
            out[item["id"]] = ["traite", proof[:200]]
        elif entry.get("repond") is True:
            out[item["id"]] = ["proche", f"preuve absente du texte : {proof[:150]}"]
        else:
            out[item["id"]] = ["proche", "ne répond pas"]
    return out


def rates(sets: dict, judged: dict, keys: tuple) -> dict[str, float]:
    count: Counter = Counter()
    for key in keys:
        for item in sets[key]:
            verdict = judged.get((key, item["id"]), "non_juge")
            count[(item["label"], verdict)] += 1
            count[item["label"]] += 1
    kept = sum(count[(label, "traite")] for label in "RTH")
    return {
        "recall": count[("R", "traite")] / max(count["R"], 1),
        "rejected": count[("R", "hors_sujet")] / max(count["R"], 1),
        "precision": count[("R", "traite")] / max(kept, 1),
        "kept": kept,
    }


def summary(folder: Path) -> None:
    sets = load(folder)
    made = calls(folder)
    print(f"{len(made)} calls, {sum(c['seconds'] for c in made) / 60:.0f} min of model,"
          f" {sum(1 for c in made if c['error'])} with an error")
    seconds = {
        v: sum(c["seconds"] for c in made if c["variant"] == v and c["key"] in REFERENCE)
        for v in ("B", "D", "E")
    }
    baseline_control = rates(sets, verdicts(made, "B", 1), CONTROLS)
    for variant in ("B", "D", "E"):
        cost = (seconds["B"] + seconds["D"]) if variant == "D" else seconds[variant]
        print(f"\n== {variant}: model time on the reference {cost / 60:.0f} min"
              f" ({cost / max(seconds['B'], 1):.1f} × B)")
        met = [cost <= COST_MAX * max(seconds["B"], 1)]
        for run_number in PASSES:
            judged = verdicts(made, variant, run_number)
            total = rates(sets, judged, REFERENCE)
            each = {k: rates(sets, judged, (k,)) for k in REFERENCE}
            cold = [i for i in sets["Pourquoi risque"] if i["label"] == "R"]
            cold_kept = sum(judged.get(("Pourquoi risque", i["id"])) == "traite" for i in cold)
            bulgaria = [i for i in sets["Quelles sont"] if "Bulgarie" in i["title"]]
            held = sum(judged.get(("Quelles sont", i["id"])) == "traite" for i in bulgaria)
            print(f"  pass {run_number}: recall {total['recall']:.1%}, rejected {total['rejected']:.1%},"
                  f" precision {total['precision']:.1%} ({total['kept']} kept),"
                  f" cold {cold_kept}/{len(cold)}, Bulgaria {held}/{len(bulgaria)}")
            for k, r in each.items():
                print(f"    {k:16} recall {r['recall']:.0%} precision {r['precision']:.0%} kept {r['kept']}")
            met += [
                total["recall"] >= RECALL_MIN, total["rejected"] <= REJECTED_MAX,
                total["precision"] >= PRECISION_MIN, cold_kept >= 5, held == 0,
                all(r["precision"] >= PRECISION_EACH_MIN for r in each.values()),
            ]
        first, second = verdicts(made, variant, 1), verdicts(made, variant, 2)
        pairs = [(k, i["id"]) for k in REFERENCE for i in sets[k]]
        either = [p for p in pairs if "traite" in (first.get(p), second.get(p))]
        both = [p for p in either if first.get(p) == second.get(p) == "traite"]
        stability = len(both) / max(len(either), 1)  # kept twice among kept at least once
        control = rates(sets, verdicts(made, variant, 1), CONTROLS)
        drop = baseline_control["recall"] - control["recall"]
        print(f"  stability {stability:.1%}; controls recall {control['recall']:.1%}"
              f" (B {baseline_control['recall']:.1%}), precision {control['precision']:.1%}")
        met += [
            stability >= STABILITY_MIN, drop <= CONTROL_RECALL_DROP_MAX,
            control["precision"] >= baseline_control["precision"],
        ]
        print(f"  criteria met: {all(met)} ({sum(met)}/{len(met)})")


if __name__ == "__main__":
    where = Path(sys.argv[1])
    if "--summary" in sys.argv:
        summary(where)
    else:
        run(where, "--pilot" in sys.argv)
