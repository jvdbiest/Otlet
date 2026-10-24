# SPDX-License-Identifier: AGPL-3.0-or-later
"""A1b bench: what qualification by a model adds to the search of the Veille (design document
« Otlet · A1b : Assistant de veille », Joël, 2026-10-24).

Three methods on the same subjects of a real Veille:
- A: the search of Otlet today, the subject as typed;
- B: the subject widened by the model into concepts with their terms in French, Dutch and
  English, then searched without a model, each term in every language of the index;
- G: B with the terms of a glossary added, as the author would edit the terms shown (the
  glossary of the design: results/glossary.json, concepts in the order of the model's);
- C: G, then each candidate judged by the model (traite, proche, hors_sujet) with a reason.

Steps, each writing JSON into results/:
  python3 bench.py expand    # B: concepts and terms, one call per subject
  python3 bench.py collect   # A and B: candidates, the union is what the reference judges
  python3 bench.py qualify   # C: verdicts and reasons, by batches
  python3 bench.py score     # against results/reference.json (the author's judgements)

Reads the database through `docker compose exec db psql` (run it from deploy/ of the
instance), and calls Ollama on OLLAMA (an address on the local network).
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OLLAMA = os.environ.get("OLLAMA", "http://192.168.129.45:11434")
MODEL = os.environ.get("MODEL", "qwen3:14b")
WORKSPACE = os.environ["WORKSPACE"]
PROJECT = os.environ.get("PROJECT", "otlet-x01")
CONFIGS = ("french", "dutch", "english", "simple")
BATCH = 25

SUBJECTS = [
    {"key": "budget-bxl", "subject": "Budget de la Région de Bruxelles-Capitale", "angle": "", "typed": "budget bruxelles"},
    {"key": "austen", "subject": "La tempête Austen", "angle": "son déroulement en Belgique", "typed": "tempête Austen"},
    {"key": "piratage-ia", "subject": "Le piratage et l'intelligence artificielle", "angle": "", "typed": "piratage IA"},
    {"key": "verstappen", "subject": "Max Verstappen", "angle": "", "typed": "Max Verstappen"},
    {"key": "apple", "subject": "La présentation Apple du 28 octobre", "angle": "les produits attendus", "typed": "Apple 28 octobre"},
    {"key": "actiris-creches", "subject": "Actiris et les crèches bruxelloises", "angle": "", "typed": "Actiris crèches"},
]


def sql(query: str) -> list[dict]:
    """Rows of a query, as JSON objects."""
    wrapped = f"SELECT coalesce(json_agg(x), '[]') FROM ({query}) x"
    out = subprocess.run(
        ["sudo", "docker", "compose", "-p", PROJECT, "exec", "-T", "db",
         "psql", "-U", "otlet", "-d", "otlet", "-tA", "-c", wrapped],
        check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    ).stdout
    return json.loads(out)


def quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def chat(system: str, user: str, schema: dict) -> tuple[dict, dict]:
    body = json.dumps({
        "model": MODEL, "stream": False, "think": False, "format": schema,
        "options": {"temperature": 0, "num_ctx": 16384},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    started = time.monotonic()
    request = urllib.request.Request(f"{OLLAMA}/api/chat", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        data = json.load(response)
    usage = {"seconds": round(time.monotonic() - started, 1),
             "tokens_in": data.get("prompt_eval_count"), "tokens_out": data.get("eval_count")}
    return json.loads(data["message"]["content"]), usage


def load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def save(name: str, data) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


EXPAND_SYSTEM = (
    "Tu prépares une recherche par mots-clés dans une veille de presse belge, en français, "
    "néerlandais et anglais. Découpe le sujet en concepts indispensables (2 au plus ; 1 si le "
    "sujet est un nom propre ou un événement). Pour chaque concept, donne les termes qui le "
    "désignent dans les trois langues. Règles : chaque terme a 1 à 3 mots ; un concept par "
    "terme, jamais deux ; pas d'année ni de date que le sujet ne donne pas ; rien d'inventé "
    "(un nom propre reste tel quel) ; pas de terme qui trouverait tout (« actualité », "
    "« Belgique » seul) ; 8 termes au plus par concept.\n"
    "Exemple, sujet « Les loyers à Bruxelles » : concepts [{name: loyer, terms: [loyer, loyers, "
    "huur, huurprijzen, rent]}, {name: Bruxelles, terms: [Bruxelles, bruxellois, Brussel, "
    "Brusselse, Brussels]}]."
)
EXPAND_SCHEMA = {
    "type": "object",
    "properties": {"concepts": {"type": "array", "items": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "terms": {"type": "array", "items": {"type": "string"}}},
        "required": ["name", "terms"]}}},
    "required": ["concepts"],
}


def expand() -> None:
    out = {}
    for s in SUBJECTS:
        answer, usage = chat(EXPAND_SYSTEM, f"Sujet : {s['subject']}\nAngle : {s['angle'] or '(aucun)'}", EXPAND_SCHEMA)
        out[s["key"]] = {"concepts": answer["concepts"], "usage": usage}
        print(s["key"], usage, [c["terms"] for c in answer["concepts"]])
    save("expand.json", out)


ITEM = (
    "SELECT i.id::text, coalesce(s.name, 'manuel') AS publisher, i.language,"
    " coalesce(i.published_at, i.collected_at)::date::text AS day, i.title,"
    " left(coalesce(i.summary, ''), 400) AS summary, i.url"
    " FROM source_items i LEFT JOIN sources s ON s.id = i.source_id"
    f" WHERE i.workspace_id = '{WORKSPACE}' AND i.duplicate_of IS NULL"
)


def matches(term: str) -> str:
    return "(" + " OR ".join(
        f"i.search @@ websearch_to_tsquery('{c}', {quote(term)})" for c in CONFIGS) + ")"


def rank(term: str) -> str:
    return "greatest(" + ", ".join(
        f"ts_rank(i.search, websearch_to_tsquery('{c}', {quote(term)}))" for c in CONFIGS) + ")"


def search(concepts: list[dict]) -> list[dict]:
    """The items holding a term of every concept, the best ranked first: no model."""
    where = " AND ".join("(" + " OR ".join(matches(t) for t in c["terms"]) + ")" for c in concepts)
    score = " + ".join(rank(t) for c in concepts for t in c["terms"])
    return sql(f"{ITEM} AND {where} ORDER BY ({score}) DESC LIMIT 60")


def collect() -> None:
    widened = load("expand.json")
    glossary = load("glossary.json") if (RESULTS / "glossary.json").exists() else {}
    out = {}
    for s in SUBJECTS:
        typed = s["typed"]
        simple = sql(f"{ITEM} AND {matches(typed)} ORDER BY {rank(typed)} DESC LIMIT 40")
        concepts = widened[s["key"]]["concepts"]
        broad = search(concepts)
        extra = glossary.get(s["key"], [])
        edited = [
            {"name": c["name"], "terms": list(dict.fromkeys([*c["terms"], *(extra[n] if n < len(extra) else [])]))}
            for n, c in enumerate(concepts)
        ]
        with_glossary = search(edited)
        union = {item["id"]: item for item in [*simple, *broad, *with_glossary]}
        out[s["key"]] = {"subject": s, "concepts": concepts, "edited": edited,
                         "A": [i["id"] for i in simple], "B": [i["id"] for i in broad],
                         "G": [i["id"] for i in with_glossary],
                         "candidates": list(union.values())}
        langs = {}
        for item in union.values():
            langs[item["language"]] = langs.get(item["language"], 0) + 1
        print(s["key"], "A", len(simple), "B", len(broad), "G", len(with_glossary), "union", len(union), langs)
    save("candidates.json", out)


QUALIFY_SYSTEM = (
    "Tu aides un auteur à constituer la matière d'un article à partir de sa veille de presse. "
    "Pour chaque élément (titre et début de résumé, dans sa langue d'origine), dis s'il traite "
    "le sujet : « traite » s'il porte sur le sujet ; « proche » s'il en parle en passant ou "
    "traite un sujet voisin ; « hors_sujet » sinon. Si un angle est donné, il oriente le jugement "
    "sans l'imposer. La raison, en français, 25 mots au plus, dit ce que traite l'élément, "
    "d'après son titre et son résumé seulement : ne déduis ni pays, ni date, ni auteur qu'ils ne "
    "donnent pas. Réponds pour chaque numéro reçu, et seulement pour eux."
)
QUALIFY_SCHEMA = {
    "type": "object",
    "properties": {"verdicts": {"type": "array", "items": {
        "type": "object",
        "properties": {"n": {"type": "integer"},
                       "verdict": {"type": "string", "enum": ["traite", "proche", "hors_sujet"]},
                       "raison": {"type": "string"}},
        "required": ["n", "verdict", "raison"]}}},
    "required": ["verdicts"],
}


def qualify() -> None:
    data = load("candidates.json")
    out = {}
    for key, entry in data.items():
        s = entry["subject"]
        broad = [i for i in entry["candidates"] if i["id"] in set(entry["G"])]
        verdicts, usages = {}, []
        for start in range(0, len(broad), BATCH):
            batch = broad[start:start + BATCH]
            lines = [f"{n}. [{i['language']}] {i['title']} — {i['summary'][:300]}" for n, i in enumerate(batch, 1)]
            user = f"Sujet : {s['subject']}\nAngle : {s['angle'] or '(aucun)'}\n\nÉléments :\n" + "\n".join(lines)
            answer, usage = chat(QUALIFY_SYSTEM, user, QUALIFY_SCHEMA)
            usages.append(usage)
            for v in answer["verdicts"]:
                if 1 <= v["n"] <= len(batch):  # an invented number is dropped, as the server would
                    verdicts[batch[v["n"] - 1]["id"]] = {"verdict": v["verdict"], "raison": v["raison"]}
        missing = [i["id"] for i in broad if i["id"] not in verdicts]
        out[key] = {"verdicts": verdicts, "missing": missing, "usage": usages}
        print(key, len(verdicts), "verdicts,", len(missing), "missing,", usages)
    save("qualify.json", out)


def score() -> None:
    data, qualified = load("candidates.json"), load("qualify.json")
    reference = load("reference.json")  # {key: {item id: traite | proche | hors_sujet}}
    report = {}
    for key, entry in data.items():
        ref = reference[key]
        relevant = {i for i, v in ref.items() if v == "traite"}
        by_id = {i["id"]: i for i in entry["candidates"]}
        verdicts = qualified[key]["verdicts"]
        kept_c = [i for i in entry["G"] if verdicts.get(i, {}).get("verdict") == "traite"]
        rows = {}
        for name, ranked in (("A", entry["A"]), ("B", entry["B"]), ("G", entry["G"]), ("C", kept_c)):
            top = ranked[:10]
            found = set(ranked) & relevant
            nl = {i for i in relevant if by_id[i]["language"].lower().startswith("nl")}
            rows[name] = {
                "precision_10": round(sum(i in relevant for i in top) / len(top), 2) if top else None,
                "recall": round(len(found) / len(relevant), 2) if relevant else None,
                "recall_nl": round(len(found & nl) / len(nl), 2) if nl else None,
                "shown": len(ranked),
            }
        wrongly_out = [i for i in relevant if verdicts.get(i, {}).get("verdict") == "hors_sujet"]
        report[key] = {"relevant": len(relevant), "methods": rows, "relevant_set_aside_by_C": wrongly_out}
        print(key, json.dumps(report[key], ensure_ascii=False))
    save("score.json", report)


if __name__ == "__main__":
    {"expand": expand, "collect": collect, "qualify": qualify, "score": score}[sys.argv[1]]()
