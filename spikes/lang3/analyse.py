"""LANG3 analysis (docs/spikes/LANG3.md).

python3 analyse.py <dir> prepare : from <dir>/lang3.jsonl, the blind reading file lecture.txt
    (L01 to L15, shuffled), the key correspondance.json and an empty grid grille.csv
    (code;faits;langue;non_traduits;notes).
python3 analyse.py <dir> aide : lecture_aide.txt, each sentence with the source sentences the
    reading aid shows (aide.jsonl, from aide.py).
python3 analyse.py <dir> score : the six criteria, from the filled grid (rapport.txt).
Needs subjects.json beside this file: the language of each source.
"""

import csv
import json
import random
import re
import statistics
import sys
from pathlib import Path

WORDS = {"short": 300, "medium": 600, "long": 1200}
REPEAT_SHARE = 0.7
LONG_WORD = 6
SUBJECTS = json.loads((Path(__file__).parent / "subjects.json").read_text(encoding="utf-8"))


def text_of(node):
    if node.get("type") == "text":
        return node.get("text", "")
    return "".join(text_of(c) for c in node.get("content") or [])


def blocks(document):
    out = []
    for node in document.get("content") or []:
        kind = node.get("type")
        if kind in ("heading", "paragraph", "blockquote"):
            t = text_of(node).strip()
            if t:
                out.append((kind, t))
    return out


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def repeated(paragraphs):
    seen, count = [], 0
    for p in paragraphs:
        for s in sentences(p):
            words = {w.lower() for w in re.findall(r"\w+", s) if len(w) >= LONG_WORD}
            if len(words) < 2:
                continue
            if any(len(words & w) >= REPEAT_SHARE * len(words) for w in seen):
                count += 1
            seen.append(words)
    return count


def cited_languages(document, subject):
    """The languages of the sources the draft cites, found by their titles."""
    titles = {s["id"]: s.get("titre", "") for s in document.get("attrs", {}).get("sources") or []}
    cited = set()

    def walk(node):
        for mark in node.get("marks") or []:
            if mark.get("type") == "source_ref":
                cited.add(mark["attrs"]["source"])
        for child in node.get("content") or []:
            walk(child)

    walk(document)
    languages = set()
    for key in cited:
        title = titles.get(key, "")
        for item in SUBJECTS[subject]["items"]:
            if title[:50] and item["title"].startswith(title[:50]) or title.startswith(item["title"][:50]):
                languages.add(item["language"])
    return languages


def load(folder):
    rows = []
    for line in (folder / "lang3.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        version = ((r.get("article") or {}).get("versions") or [None])[-1]
        document = version["document"] if version else {}
        r["blocks"] = blocks(document) if version else []
        prose = [t for k, t in r["blocks"] if k != "heading"]
        r["words"] = sum(len(t.split()) for t in prose)
        r["repeated"] = repeated(prose)
        details = (version or {}).get("details") or {}
        r["written"] = details.get("language_written")
        r["reason"] = details.get("model_reason")
        r["model"] = (version or {}).get("model")
        r["used"] = (details.get("brief") or {}).get("length_used") or "medium"
        r["cited"] = sorted(cited_languages(document, r["subject"])) if version else []
        rows.append(r)
    return rows


def prepare(folder):
    rows = load(folder)
    order = list(range(len(rows)))
    random.Random(1111).shuffle(order)
    key, lines = {}, []
    for n, i in enumerate(order, 1):
        r = rows[i]
        code = f"L{n:02d}"
        key[code] = {"subject": r["subject"], "language": r["language"], "brief": r["brief"]}
        lines.append(f"===== {code} | {r['subject']} | {r['language']} | {r['words']} mots =====")
        if not r["blocks"]:
            lines.append(f"(pas de brouillon : {r['status']} {r.get('error') or ''})")
        for kind, t in r["blocks"]:
            lines.append(("## " if kind == "heading" else "") + t)
        lines.append("")
    (folder / "lecture.txt").write_text("\n".join(lines), encoding="utf-8")
    (folder / "correspondance.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    grid = folder / "grille.csv"
    if not grid.exists():
        with grid.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["code", "faits", "langue", "non_traduits", "notes"])
            for code in key:
                w.writerow([code, "", "", "", ""])
    print(len(rows), "brouillons")


def aide(folder):
    key = json.loads((folder / "correspondance.json").read_text(encoding="utf-8"))
    checks = {}
    for line in (folder / "aide.jsonl").read_text(encoding="utf-8").splitlines():
        a = json.loads(line)
        checks[a["brief"]] = a["checks"]
    rows = {r["brief"]: r for r in load(folder)}
    lines = []
    for code, k in key.items():
        r = rows[k["brief"]]
        lines.append(f"===== {code} | {k['subject']} | {k['language']} | {r['words']} mots =====")
        for kind, t in r["blocks"]:
            if kind == "heading":
                lines.append("## " + t)
        for c in checks.get(k["brief"], []):
            lines.append("> " + c["sentence"])
            for s in c["shown"][:2]:
                lines.append(f"    [{s['key']}] {s['sentence'][:300]}")
        lines.append("")
    (folder / "lecture_aide.txt").write_text("\n".join(lines), encoding="utf-8")
    print(folder / "lecture_aide.txt")


def score(folder):
    rows = {r["brief"]: r for r in load(folder)}
    key = json.loads((folder / "correspondance.json").read_text(encoding="utf-8"))
    with (folder / "grille.csv").open(encoding="utf-8") as f:
        for g in csv.DictReader(f, delimiter=";"):
            r = rows[key[g["code"]]["brief"]]
            r["facts"] = int(g["faits"] or 0)
            r["faults"] = int(g["langue"] or 0)
            r["untranslated"] = int(g["non_traduits"] or 0)
            r["code"] = g["code"]
    rs = list(rows.values())
    m1 = sum(1 for r in rs if r["status"] == "done" and r["written"] == r["language"]
             and r["reason"] == "language")
    m2 = sum(1 for r in rs if set(r["cited"]) >= {"fr", "nl", "en"})
    m3 = sum(r.get("facts", 0) for r in rs)
    m3max = max((r.get("facts", 0) for r in rs), default=0)
    m4 = {lang: sum(r.get("faults", 0) for r in rs if r["language"] == lang) for lang in ("fr", "nl", "en")}
    m5 = sum(r.get("untranslated", 0) for r in rs)
    m6 = sum(1 for r in rs if r["words"] >= 0.7 * WORDS[r["used"]])
    med = statistics.median(r["seconds"] for r in rs) / 60
    out = [
        "Par brouillon :",
        *(f"{r.get('code', '?')} {r['subject']:9} {r['language']} {r['status']} {r['model']} {r['reason']}"
          f" écrit {r['written']} cite {','.join(r['cited'])} {r['words']} mots {r['seconds']} s"
          f" répétées {r['repeated']} faits {r.get('facts')} langue {r.get('faults')}"
          f" non traduits {r.get('untranslated')}" for r in sorted(rs, key=lambda r: (r['subject'], r['language']))),
        "",
        f"M1 aboutis, bonne langue, modèle de la langue : {m1}/15 (15)",
        f"M2 sources des trois langues citées : {m2}/15 (≥ 12)",
        f"M3 erreurs de faits : {m3} (≤ 15), au plus {m3max} par brouillon (≤ 3)",
        f"M4 fautes de langue : {m4} (≤ 20 par langue)",
        f"M5 passages non traduits : {m5} (≤ 2)",
        f"M6 longueur : {m6}/15 (15), durée médiane {med:.1f} min (≤ 10)",
    ]
    text = "\n".join(out)
    (folder / "rapport.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    {"prepare": prepare, "aide": aide, "score": score}[sys.argv[2]](Path(sys.argv[1]))
