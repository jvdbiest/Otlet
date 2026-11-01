# SPDX-License-Identifier: AGPL-3.0-or-later
import json, re, statistics as st, sys
exec(open("rules.py", encoding="utf-8").read())
lines = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
changed = lines[-1]["changed"]; rows = lines[:-1]
def rel(x, rules):
    t = f"{x['t']} {x['s']}".lower()
    return all(re.search(r, t) for r in rules)
b = [len(r["before"]) for r in rows]; a = [len(r["after"]) for r in rows]
print(f"{len(rows)} questions; set median {st.median(b)} -> {st.median(a)}, mean {st.mean(b):.0f} -> {st.mean(a):.0f}, max {max(b)} -> {max(a)}")
print("questions with a set that shrinks:", sum(1 for x,y in zip(a,b) if x<y), "| empty before/after:", sum(1 for x in b if x==0), sum(1 for x in a if x==0))
print("\nreference: relevant in top 30 / in set / set size, before -> after")
for r in rows:
    rules = RULES.get(r["q"])
    if not rules: continue
    f = lambda s: f"{sum(1 for x in s[:30] if rel(x,rules)):>2}/{sum(1 for x in s if rel(x,rules)):>2}/{len(s):>3}"
    print(f"  {r['q'][:50]:50} {f(r['before'])} -> {f(r['after'])}")
print("\nwords of the top 30 replaced (kept of the 30 before):")
kept = []
for r in rows:
    B = {x['id'] for x in r['before'][:30]}; A = {x['id'] for x in r['after'][:30]}
    if B: kept.append(len(A & B) / len(B))
print(f"  median share kept {st.median(kept):.2f}")
print(f"\nguard changes {len(changed)} turns:")
for c in changed: print(f"  [{c['pos']}/{c['op']}] {c['q'][:70]} : {c['before']} -> {c['after']}")
for r in rows:
    if "risque t" in r["q"]:
        print("\nWEATHER", r["before_c"], "->", r["after_c"], "words", r["words_before"], "->", r["words_after"], "near", r["near_before"], "->", r["near_after"], "best", r["best"])
        for n, x in enumerate(r["after"][:40]):
            print(f"  {n:2d} {x['t'][:100]}")
