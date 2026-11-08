# SPDX-License-Identifier: AGPL-3.0-or-later
"""After REL1 (outside its protocol, docs/spikes/REL1.md §4): the same aid for the faulty sentence
alone. Run beside rel1.py and frozen.json:  python3 apres_phrase.py"""
import json, math, re
from collections import Counter
import rel1
drafts = json.load(open("frozen.json", encoding="utf-8"))
documents = [s for d in drafts for s in d["sources"]]
df = Counter(t for s in documents for t in rel1.tokens(s))
idf = {t: math.log((1 + len(documents)) / (1 + n)) + 1 for t, n in df.items()}
SENT = {"MotoGP, Martín deuxième": r"terminant deuxi", "MotoGP, Zarco 281 points": r"Johann Zarco, cinqui",
        "Dana White devenu « elle »": r"photo la repr", "Printemps devenu avril": r"avril 2026",
        "Citation à moitié traduite": r"btw-nummer est het"}
for name, (brief, where, reveal) in rel1.CASES.items():
    for d in drafts:
        if d["brief"] != brief: continue
        hit = None
        for p in d["paragraphs"]:
            if re.search(where, p["text"]):
                sentence = next(s for s in rel1.SENTENCE.split(p["text"]) if re.search(SENT[name], s))
                got = rel1.shown(sentence, rel1._cited_sources(d, p), idf)
                hit = next((n + 1 for n, (_, s) in enumerate(got) if re.search(reveal, s)), 0)
                print(name, "| sentence-level:", "rank " + str(hit) if hit else "not revealed", "| shown", len(got))
                if not hit: print("   ", [s[:120] for _, s in got])
                break
        if hit is not None: break
