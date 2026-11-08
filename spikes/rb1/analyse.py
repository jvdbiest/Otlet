# SPDX-License-Identifier: AGPL-3.0-or-later
"""RB1 (docs/spikes/RB1.md §4): search, sort, stability and P3 measures from ask.jsonl.
Run beside questions.json and ask.jsonl:  python3 analyse.py  -> results/mesures.txt"""

import json, re
spec = {q["n"]: q for q in json.load(open("questions.json"))["questions"]}
CORPUS_R = {1: 7, 2: 11, 3: 5, 4: 6, 5: 7, 6: 21, 7: 1, 8: 2, 9: 3, 10: 6, 11: 11, 12: 4, 13: 1, 14: 0}
def lab(s, t):
    if any(re.search(p, t, re.I) for p in s["R"]): return "R"
    if any(re.search(p, t, re.I) for p in s["C"]): return "C"
    return "x"
tot = dict(Rc=0, Rf=0, kept=0, keptR=0, Rfound_judged=0, R_aside=0, either=0, both=0)
for l in open("ask.jsonl"):
    d = json.loads(l); s = spec[d["n"]]
    labs = {c["id"]: lab(s, c["title"]) for c in d["candidates"]}
    Rf = sum(v == "R" for v in labs.values())
    tot["Rc"] += CORPUS_R[d["n"]]; tot["Rf"] += Rf
    line = f'Q{d["n"]:<2} set {len(d["candidates"]):3} R found {Rf}/{CORPUS_R[d["n"]]}'
    if d["sorts"]:
        v1 = {k: v[0] for k, v in d["sorts"][0]["verdicts"].items()}
        v2 = {k: v[0] for k, v in d["sorts"][1]["verdicts"].items()}
        kept = [k for k, v in v1.items() if v == "traite"]
        close = [k for k, v in v1.items() if v not in ("traite", "hors_sujet")]
        keptR = sum(labs[k] == "R" for k in kept)
        aside = sum(labs[k] == "R" and v1.get(k) == "hors_sujet" for k in labs)
        either = [k for k in labs if "traite" in (v1.get(k), v2.get(k))]
        both = [k for k in either if v1.get(k) == v2.get(k) == "traite"]
        opens = len(kept) > 20 or len(close) >= 3
        needed = any(labs[k] != "R" for k in kept)
        tot["kept"] += len(kept); tot["keptR"] += keptR; tot["Rfound_judged"] += Rf; tot["R_aside"] += aside
        tot["either"] += len(either); tot["both"] += len(both)
        line += f' | kept {len(kept)} (R {keptR}, nonR {len(kept)-keptR}) close {len(close)} | R not kept {Rf-keptR} R aside {aside} | stable {len(both)}/{len(either)} | P3 opens {opens} needed {needed}'
        nonR = [c["title"][:45] for c in d["candidates"] if c["id"] in kept and labs[c["id"]] != "R"]
        if nonR: line += f'\n      kept non-R: {nonR}'
    print(line)
    print("      op", d["operation"], "| fact:", (json.dumps(d["fact"], ensure_ascii=False)[:300] if d["fact"] else None))
print(tot)
print("search recall %.1f%%, precision %.1f%%, recall %.1f%%, aside %.1f%%, stability %.1f%%" % (
    100*tot["Rf"]/tot["Rc"], 100*tot["keptR"]/tot["kept"], 100*tot["keptR"]/tot["Rfound_judged"],
    100*tot["R_aside"]/tot["Rfound_judged"], 100*tot["both"]/tot["either"]))
