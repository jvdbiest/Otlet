"""LANG1 analysis (docs/spikes/LANG1.md).

python3 analyse.py <dir> prepare : from <dir>/lang1.jsonl, writes the blind reading file
    lecture.txt (drafts shuffled, L01 to L45, no model named), the key correspondance.json and
    an empty grid grille.csv (code;faits;langue;notes) to fill while reading.
python3 analyse.py <dir> score : with the filled grid, the six criteria per language and model,
    the best model of each language and its stability over the subjects (rapport.txt).
"""

import csv
import json
import random
import re
import statistics
import sys
from pathlib import Path

ASKED = 600  # medium
LIMIT_MEDIAN = 600  # seconds
REPEAT_SHARE = 0.7
LONG_WORD = 6


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
        elif kind in ("bulletList", "orderedList"):
            for item in node.get("content") or []:
                t = text_of(item).strip()
                if t:
                    out.append(("item", t))
    return out


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def repeated(paragraphs):
    seen = []
    count = 0
    for p in paragraphs:
        for s in sentences(p):
            words = {w.lower() for w in re.findall(r"\w+", s) if len(w) >= LONG_WORD}
            if len(words) < 2:
                continue
            if any(len(words & w) >= REPEAT_SHARE * len(words) for w in seen):
                count += 1
            seen.append(words)
    return count


def load(folder):
    rows = []
    for line in (folder / "lang1.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        version = ((r.get("article") or {}).get("versions") or [None])[-1]
        r["blocks"] = blocks(version["document"]) if version else []
        prose = [t for k, t in r["blocks"] if k != "heading"]
        r["words"] = sum(len(t.split()) for t in prose)
        r["repeated"] = repeated(prose)
        details = r.get("details") or {}
        r["written"] = details.get("language_written")
        r["used"] = (details.get("brief") or {}).get("length_used") or "medium"
        rows.append(r)
    return rows


def prepare(folder):
    rows = load(folder)
    order = list(range(len(rows)))
    random.Random(1110).shuffle(order)
    key = {}
    lines = []
    for n, i in enumerate(order, 1):
        r = rows[i]
        code = f"L{n:02d}"
        key[code] = {"subject": r["subject"], "language": r["language"], "model": r["model"],
                     "brief": r["brief"]}
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
            w.writerow(["code", "faits", "langue", "notes"])
            for code in key:
                w.writerow([code, "", "", ""])
    print(len(rows), "brouillons ;", folder / "lecture.txt")


def aide(folder):
    """lecture_aide.txt: the blind reading file, each sentence followed by the source sentences
    the reading aid shows for it (aide.jsonl, from aide.py), two at most, cut at 300 characters."""
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
        if not r["blocks"]:
            lines.append(f"(pas de brouillon : {r['status']} {r.get('error') or ''})")
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
    rows = {(r["subject"], r["language"], r["model"]): r for r in load(folder)}
    key = json.loads((folder / "correspondance.json").read_text(encoding="utf-8"))
    with (folder / "grille.csv").open(encoding="utf-8") as f:
        for g in csv.DictReader(f, delimiter=";"):
            k = key[g["code"]]
            r = rows[(k["subject"], k["language"], k["model"])]
            r["facts"] = int(g["faits"] or 0)
            r["faults"] = int(g["langue"] or 0)
            r["code"] = g["code"]
    out = []
    languages = sorted({k[1] for k in rows})
    models = sorted({k[2] for k in rows})
    subjects = sorted({k[0] for k in rows})
    for lang in languages:
        out.append(f"== {lang}")
        kept = []
        for model in models:
            rs = [rows[(s, lang, model)] for s in subjects if (s, lang, model) in rows]
            c1 = sum(1 for r in rs if r["status"] == "done" and r["written"] == lang)
            c2 = sum(r.get("facts", 0) for r in rs)
            c3 = sum(r.get("faults", 0) for r in rs)
            c4 = sum(1 for r in rs if r["repeated"] > 2)
            c5 = sum(1 for r in rs if r["words"] >= 0.7 * {"short": 300, "medium": 600,
                                                            "long": 1200}[r["used"]])
            med = statistics.median(r["seconds"] for r in rs) if rs else 0
            ok = (c1 == 5, c2 <= 5, c3 <= 20, c4 == 0, c5 == 5, med <= LIMIT_MEDIAN)
            out.append(f"{model:22} C1 {c1}/5  C2 {c2}  C3 {c3}  C4 {c4}  C5 {c5}/5  "
                       f"C6 {med / 60:.1f} min  mots {[r['words'] for r in rs]}  "
                       f"répétées {[r['repeated'] for r in rs]}  "
                       f"{'RETENU' if all(ok) else 'non retenu'}")
            if all(ok):
                kept.append((c2, c3, model))
        if kept:
            best = sorted(kept)[0][2]
            firsts = 0
            for s in subjects:
                points = {m: 3 * rows[(s, lang, m)].get("facts", 0) + rows[(s, lang, m)].get(
                    "faults", 0) for m in models if (s, lang, m) in rows}
                if points.get(best) == min(points.values()):
                    firsts += 1
            out.append(f"meilleur : {best}, premier ou ex aequo sur {firsts} sujets sur "
                       f"{len(subjects)} : {'stable' if firsts >= 3 else 'pas stable'}")
        else:
            out.append("aucun modèle retenu")
    text = "\n".join(out)
    (folder / "rapport.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    {"prepare": prepare, "aide": aide, "score": score}[sys.argv[2]](folder)
