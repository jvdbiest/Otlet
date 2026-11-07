# SPDX-License-Identifier: AGPL-3.0-or-later
"""TRI2, reading of the errors (docs/spikes/TRI2.md §4): run beside tri2.py in the data folder,
   python3 analyse.py  -> results/analyse.txt"""

import json, sys, collections
sys.path.insert(0, ".")
import tri2
from pathlib import Path
F = Path(".")
sets = tri2.load(F); made = tri2.calls(F)
byid = {(k, i["id"]): i for k, v in sets.items() for i in v}
REF = tri2.REFERENCE
# D stage: what it removed, by label and reason
for run in (1, 2):
    b = tri2.verdicts(made, "B", run)
    cnt = collections.Counter()
    for c in made:
        if c["variant"] == "D" and c["pass"] == run:
            for iid, (v, why) in c["verdicts"].items():
                lab = byid[(c["key"], iid)]["label"]
                kind = "kept" if v == "traite" else ("noproof" if why.startswith("preuve absente") else ("noanswer" if why == "sans réponse" else "saysno"))
                cnt[(lab, kind)] += 1
    print("D stage pass", run, dict(sorted(cnt.items())))
print("\nD removed R items (reference):")
for c in made:
    if c["variant"] == "D" and c["key"] in REF:
        for iid, (v, why) in c["verdicts"].items():
            it = byid[(c["key"], iid)]
            if it["label"] == "R" and v != "traite":
                print(" ", c["pass"], c["key"][:8], it["rank"], it["title"][:70], "|", why[:110])
print("\nNon-R kept in B, by number of B passes (reference):")
b1, b2 = tri2.verdicts(made, "B", 1), tri2.verdicts(made, "B", 2)
for k in REF:
    for it in sets[k]:
        n = (b1.get((k, it["id"])) == "traite") + (b2.get((k, it["id"])) == "traite")
        if it["label"] != "R" and n:
            print(" ", k[:8], it["label"], n, it["rank"], it["title"][:80])
print("\nR not kept in B:")
for k in REF:
    for it in sets[k]:
        if it["label"] == "R":
            v = (b1.get((k, it["id"])), b2.get((k, it["id"])))
            if v != ("traite", "traite"):
                print(" ", k[:8], v, it["rank"], it["title"][:80])
print("\nE: batches with many kept non-R (pass, key, start, nonR kept):")
for c in made:
    if c["variant"] in ("B", "E") and c["key"] in REF:
        nr = sum(1 for iid, (v, _) in c["verdicts"].items() if v == "traite" and byid[(c["key"], iid)]["label"] != "R")
        if nr >= 3:
            print(" ", c["variant"], c["pass"], c["key"][:8], c["start"], nr)
