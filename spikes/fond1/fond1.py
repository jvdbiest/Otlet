# SPDX-License-Identifier: AGPL-3.0-or-later
"""FOND1: docs/spikes/FOND1.md §3. Standard library only: it runs on the VM itself.

    OLLAMA_URL=http://… python3 fond1.py <folder>     the 38 calls, one at a time; resumes
    python3 fond1.py <folder> --summary               the criteria, without texts

<folder> holds drafts.jsonl and sources.jsonl (extract.sql), and receives calls.jsonl.
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
MODEL = "qwen3:14b"
MAX_SECONDS = 3600
PASSES = (1, 2)
REFERENCES = re.compile(r"\s*\[\d+\]")
THINK = re.compile(r"<think>.*?</think>", re.S)
RULES = """Tu vérifies un paragraphe face aux sources qu'il cite. Compare uniquement aux sources \
ci-dessous, sans tes propres connaissances.

Réponds "deforme" si une affirmation du paragraphe dit autre chose que les sources, ou affirme \
ce qu'elles ne disent pas. Réponds "fidele" si tout ce qu'il affirme s'y trouve, même reformulé \
ou résumé.

Réponds en JSON : "verdict" ("fidele" ou "deforme") ; "affirmation", l'affirmation en cause, \
vide si fidèle ; "phrase_source", la phrase des sources la plus proche, recopiée telle quelle ; \
"raison", en une phrase."""
SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["fidele", "deforme"]},
        "affirmation": {"type": "string"},
        "phrase_source": {"type": "string"},
        "raison": {"type": "string"},
    },
    "required": ["verdict", "affirmation", "phrase_source", "raison"],
}


def fold(text):
    text = unicodedata.normalize("NFKD", text.casefold().replace("’", "'"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def words(text):
    return " ".join(re.findall(r"\w+", fold(text)))


def read_jsonl(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as lines:
        return [json.loads(line) for line in lines if line.strip()]


def load(folder):
    """Each case with its paragraph and the text of its cited sources."""
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    drafts = {d["article"]: d["body_text"] for d in read_jsonl(folder / "drafts.jsonl")}
    sources = {(s["article"], s["n"]): s for s in read_jsonl(folder / "sources.jsonl")}
    for case in cases:
        if "text" in case:
            case["paragraph"] = case["text"]
        else:
            start = fold(case["start"])
            lines = [x for x in drafts[case["article"]].splitlines() if fold(x).startswith(start)]
            if len(lines) != 1:
                sys.exit(f"{case['id']}: {len(lines)} paragraphs start with {case['start']!r}")
            case["paragraph"] = REFERENCES.sub("", lines[0]).strip()
        case["cited"] = [sources[(case["article"], n)] for n in case["sources"]]
    return cases


def prompt(case):
    cited = "\n\n".join(f"SOURCE {s['n']} : {s['title']}\n{s['text']}" for s in case["cited"])
    return f"{RULES}\n\n{cited}\n\nPARAGRAPHE À VÉRIFIER :\n{case['paragraph']}"


def call(url, case, seed):
    body = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "format": SCHEMA,
        "options": {"temperature": 0.2, "seed": seed, "num_ctx": 8192, "num_predict": 600},
        "messages": [{"role": "user", "content": prompt(case)}],
    }
    request = urllib.request.Request(  # noqa: S310 (the address of the local model)
        f"{url}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
        return json.load(response)


def run(folder):
    url = os.environ["OLLAMA_URL"].rstrip("/")
    cases = load(folder)
    path = folder / "calls.jsonl"
    done = {(c["id"], c["pass"]) for c in read_jsonl(path)}
    started = time.monotonic()
    for number in PASSES:
        for case in cases:
            if (case["id"], number) in done:
                continue
            if time.monotonic() - started > MAX_SECONDS:
                print("1 h reached: stopping (FOND1 §3)", flush=True)
                return
            began = time.monotonic()
            answer = call(url, case, number)
            row = {
                "id": case["id"],
                "pass": number,
                "seconds": round(time.monotonic() - began, 1),
                "prompt_tokens": answer.get("prompt_eval_count"),
                "output": THINK.sub("", answer["message"]["content"]).strip(),
            }
            with path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
            print({k: row[k] for k in ("id", "pass", "seconds", "prompt_tokens")}, flush=True)
            time.sleep(2)
    print("done", flush=True)


def summary(folder):
    cases = {c["id"]: c for c in load(folder)}
    rows = []
    for row in read_jsonl(folder / "calls.jsonl"):
        case = cases[row["id"]]
        try:
            answer = json.loads(row["output"])
        except ValueError:
            answer = {"verdict": "invalid", "affirmation": "", "phrase_source": "", "raison": ""}
        said = fold(f"{answer['affirmation']} {answer['raison']}")
        rows.append(
            {
                "id": row["id"],
                "pass": row["pass"],
                "seconds": row["seconds"],
                "prompt_tokens": row["prompt_tokens"],
                "verdict": answer["verdict"],
                "on_the_defect": any(fold(w) in said for w in case.get("defect", [])),
                "quote_found": bool(answer["phrase_source"].strip())
                and words(answer["phrase_source"]) in words(" ".join(s["text"] for s in case["cited"])),
            }
        )
    passes = {}
    for number in PASSES:
        of = [r for r in rows if r["pass"] == number]
        scored = [r for r in of if not cases[r["id"]].get("outside")]
        found = [r["id"] for r in scored if cases[r["id"]]["deformed"] and r["verdict"] == "deforme" and r["on_the_defect"]]
        passes[number] = {
            "C1_found": found,
            "C1": len(found),
            "deforme_other_reason": [r["id"] for r in scored if cases[r["id"]]["deformed"] and r["verdict"] == "deforme" and not r["on_the_defect"]],
            "C2_false_alerts": [r["id"] for r in scored if not cases[r["id"]]["deformed"] and r["verdict"] == "deforme"],
            "invalid": [r["id"] for r in of if r["verdict"] == "invalid"],
            "D7": next((r["verdict"] for r in of if r["id"] == "D7"), None),
            "quotes_found": sum(r["quote_found"] for r in of),
            "calls": len(of),
        }
    print(json.dumps({"passes": passes, "rows": rows}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if "--summary" in sys.argv:
        summary(Path(sys.argv[1]))
    else:
        run(Path(sys.argv[1]))
