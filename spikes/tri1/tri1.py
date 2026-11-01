# SPDX-License-Identifier: AGPL-3.0-or-later
"""TRI1: docs/spikes/TRI1.md §3. Three ways of sorting the same frozen sets, through the gateway of
the product and the author's own model, one call at a time.

Run in the worker container (run-tri1.sh):  python tri1.py <folder> [--pilot]
Read anywhere, standard library only:       python3 tri1.py <folder> --summary

<folder> holds items.jsonl and labels.csv, and receives calls.jsonl. Finished batches are skipped.
"""

import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

USER = "1fd3f00a-87b4-4473-aaf9-db737556c1b8"
BATCH = 25
OUTPUT_TOKENS = 8192
MAX_SECONDS = 3 * 3600
SUBJECTS = {  # the concepts of the real trial of 2026-11-01, as the product joins them
    "Pourquoi risque": "cause de la baisse des températures",
    "La situation": "situation financière des hôpitaux Flandre",
    "Que rachète": "Ahold Delhaize",
    "Quelles sont": "Ukraine",
    "Les pertes": "pertes d'emploi Belgique",
    "Les essais": "essais de motos",
    "Les prix": "prix de l'énergie cet hiver augmenter",
}
ANSWERS_SYSTEM = (
    "Tu aides un auteur à choisir, dans sa veille de presse, les articles qui servent à répondre "
    "à sa question. Pour chaque élément (titre et début de résumé, dans sa langue d'origine), "
    "d'après ce qu'il écrit :\n"
    "- « traite » : il répond à la question, ou la question porte sur son sujet principal ;\n"
    "- « proche » : même thème sans répondre, ou le sujet n'y est qu'un contexte, une mention, "
    "une conséquence lointaine ;\n"
    "- « hors_sujet » : aucun lien écrit avec la question.\n"
    "Un mot en commun ne suffit pas : pour une question sur une grève des trains, un article sur "
    "une élection où cette grève est évoquée est « proche », pas « traite ». L'absence d'un mot "
    "de la question n'écarte pas : un article peut répondre avec d'autres mots. Le pays de "
    "l'éditeur est donné entre crochets. Ne relie jamais l'élément à la question par un fait qu'il "
    "n'écrit pas. La raison, en français, 25 mots au plus, dit ce que traite l'élément. Réponds "
    "pour chaque numéro reçu, et seulement pour eux."
)
VARIANTS = ("A", "B", "C")
PASSES = {"R_in_traite": 0.85, "R_rejected": 0.03, "precision": 0.75, "H_in_traite": 0.05}


def load(folder: Path) -> dict[str, list[dict]]:
    labels = {
        (row["question"], int(row["rank"])): row
        for row in csv.DictReader((folder / "labels.csv").open(encoding="utf-8"))
    }
    sets: dict[str, list[dict]] = {}
    for line in (folder / "items.jsonl").open(encoding="utf-8"):
        item = json.loads(line)
        key = next((k for k in SUBJECTS if item["question"].startswith(k)), None)
        if key is not None:
            assert labels[(key, item["rank"])]["id"] == item["id"]
            sets.setdefault(key, []).append({**item, "label": labels[(key, item["rank"])]["label"]})
    return sets


def calls(folder: Path) -> list[dict]:
    path = folder / "calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8")]


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
    done = {(c["variant"], c["key"], c["start"]) for c in calls(folder) if c.get("verdicts")}
    started = time.monotonic()
    sets = load(folder)
    for variant in VARIANTS:
        for key, items in sets.items():
            sent = [i for i in items if i["summary"].strip()]
            for start in range(0, len(sent), BATCH):
                if (variant, key, start) in done:
                    continue
                if time.monotonic() - started > MAX_SECONDS:
                    print("max duration reached", flush=True)
                    return
                batch = sent[start : start + BATCH]
                lines = [
                    Line(
                        i["title"], i["summary"], i["language"], i["publisher"],
                        publisher_country(i["url"]),
                    )
                    for i in batch
                ]
                question = items[0]["question"]
                subject = SUBJECTS[key] if variant == "A" else question
                system = ANSWERS_SYSTEM if variant == "C" else QUALIFY_SYSTEM
                began = time.monotonic()
                asked = model.ask(
                    UUID(USER), system, qualify_message(subject, "", lines), QUALIFY_SCHEMA,
                    check_qualify, OUTPUT_TOKENS,
                )
                judged = read_qualify(asked.text, len(batch)) if asked.text else {}
                record = {
                    "variant": variant, "key": key, "start": start,
                    "seconds": round(time.monotonic() - began, 1), "error": asked.error,
                    "verdicts": {
                        batch[n - 1]["id"]: [j.verdict.value, j.reason] for n, j in judged.items()
                    },
                }
                with (folder / "calls.jsonl").open("a", encoding="utf-8") as out:
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(variant, key, start, record["seconds"], len(judged), flush=True)
                if pilot:
                    return
                time.sleep(5)
    print("complete", flush=True)


def summary(folder: Path) -> None:
    sets = load(folder)
    made = calls(folder)
    seconds = sum(c["seconds"] for c in made)
    print(f"{len(made)} calls, {seconds / 60:.0f} min of model")
    for variant in VARIANTS:
        verdicts = {
            (c["key"], item): v[0]
            for c in made
            if c["variant"] == variant
            for item, v in c["verdicts"].items()
        }
        total: Counter = Counter()
        others: Counter = Counter()
        print(f"\n{variant}: question / R in traite, R rejected, traite, R of traite, H in traite")
        for key, items in sets.items():
            count: Counter = Counter()
            for item in items:
                if not item["summary"].strip():
                    continue
                verdict = verdicts.get((key, item["id"]), "non_juge")
                count[(item["label"], verdict)] += 1
                count[item["label"]] += 1
            total.update(count)
            if key != "Quelles sont":
                others.update(count)
            print(f"  {key:16} {line(count)}")
        print(f"  {'TOTAL':16} {line(total)}")
        rates = measures(total)
        without = measures(others)
        print("  " + " ; ".join(f"{k} {v:.1%}" for k, v in rates.items()))
        print("  sans Ukraine : " + " ; ".join(f"{k} {v:.1%}" for k, v in without.items()))
        cold = [i for i in sets["Pourquoi risque"] if i["label"] == "R"]
        kept = sum(verdicts.get(("Pourquoi risque", i["id"])) == "traite" for i in cold)
        bulgaria = [i for i in sets["Quelles sont"] if "Bulgarie" in i["title"]]
        held = sum(verdicts.get(("Quelles sont", i["id"])) == "traite" for i in bulgaria)
        met = (
            all(
                r["R_in_traite"] >= PASSES["R_in_traite"]
                and r["R_rejected"] <= PASSES["R_rejected"]
                and r["precision"] >= PASSES["precision"]
                and r["H_in_traite"] <= PASSES["H_in_traite"]
                for r in (rates, without)
            )
            and kept >= 5
            and held == 0
        )
        print(f"  froid {kept}/{len(cold)} ; Bulgarie {held}/{len(bulgaria)} ; seuils tenus : {met}")


def line(count: Counter) -> str:
    traite = sum(count[(label, "traite")] for label in "RTH")
    return (
        f"{count[('R', 'traite')]}/{count['R']}, {count[('R', 'hors_sujet')]}, {traite}, "
        f"{count[('R', 'traite')]}/{traite}, {count[('H', 'traite')]}/{count['H']}"
    )


def measures(count: Counter) -> dict[str, float]:
    traite = sum(count[(label, "traite")] for label in "RTH")
    return {
        "R_in_traite": count[("R", "traite")] / max(count["R"], 1),
        "R_rejected": count[("R", "hors_sujet")] / max(count["R"], 1),
        "precision": count[("R", "traite")] / max(traite, 1),
        "H_in_traite": count[("H", "traite")] / max(count["H"], 1),
    }


if __name__ == "__main__":
    where = Path(sys.argv[1])
    if "--summary" in sys.argv:
        summary(where)
    else:
        run(where, "--pilot" in sys.argv)
