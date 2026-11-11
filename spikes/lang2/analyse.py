"""LANG2 analysis (docs/spikes/LANG2.md): python3 analyse.py <dir with lang2.jsonl>.

Per model and charter: drafts that hold the language of the brief (language_written), first
answers already in that language (no « language: » refusal), drafts that finish, words, time.
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def words(document):
    def text(node):
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(text(c) for c in node.get("content") or [])

    return sum(
        len(text(n).split())
        for n in document.get("content") or []
        if n.get("type") != "heading"
    )


folder = Path(sys.argv[1])
groups = defaultdict(list)
lines = []
for raw in (folder / "lang2.jsonl").read_text(encoding="utf-8").splitlines():
    r = json.loads(raw)
    d = r.get("details") or {}
    refusals = d.get("refusals") or []
    first_wrong = bool(refusals) and any(e.startswith("language:") for e in refusals[0])
    written = d.get("language_written")
    versions = (r.get("article") or {}).get("versions") or []
    n = words(versions[-1]["document"]) if versions else 0
    done = r["status"] == "done"
    row = {
        "held": done and written == r["language"],
        "first_held": done and not first_wrong,
        "done": done,
        "words": n,
        "seconds": r["seconds"],
        "kept_first": d.get("kept_first_answer"),
    }
    groups[(r["model"], r["charter"])].append(row)
    lines.append(
        f"{r['model']:15} {r['charter']} {r['subject']:9} {r['language']} {r['status']:7}"
        f" écrit {written} première {'autre' if first_wrong else 'bonne'} {n} mots {r['seconds']} s"
    )

out = ["Par brouillon :", *lines, "", "Par modèle et charte :"]
for (model, charter), rows in sorted(groups.items()):
    out.append(
        f"{model:15} {charter}  tient la langue {sum(x['held'] for x in rows)}/{len(rows)}"
        f"  première réponse dans la langue {sum(x['first_held'] for x in rows)}/{len(rows)}"
        f"  aboutis {sum(x['done'] for x in rows)}/{len(rows)}"
        f"  mots médians {statistics.median(x['words'] for x in rows):.0f}"
        f"  durée médiane {statistics.median(x['seconds'] for x in rows) / 60:.1f} min"
    )
text = "\n".join(out)
(folder / "rapport.txt").write_text(text, encoding="utf-8")
print(text)
