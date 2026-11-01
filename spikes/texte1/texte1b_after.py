# SPDX-License-Identifier: AGPL-3.0-or-later
"""TEXTE1b, after the conclusion: exploration, outside the protocol (§8 of the report). Is the
marker reliable; which pages E2 loses; and E3, E2 with a fallback on what the page marks. Chosen
after seeing the results on the same pages: a hypothesis to measure on other pages, not a result."""

import base64
import gzip
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

sys.path.append(os.environ.get("TEXTE1B_EXTRA", ""))
sys.path.insert(0, "/scripts")
from gold_blocks import blocks  # noqa: E402
from texte1b import coverage, pollution, structured  # noqa: E402

import trafilatura  # noqa: E402

folder = Path(sys.argv[1])
gold = json.loads(Path("/scripts/gold.json").read_text(encoding="utf-8"))
results = {}
for line in (folder / "results.jsonl").open(encoding="utf-8"):
    row = json.loads(line)
    results[row["id"]] = row
sizes = defaultdict(list)
rows = []
for line in (folder / "pages.jsonl").open(encoding="utf-8"):
    page = json.loads(line)
    if page.get("status") != 200 or not page.get("html"):
        continue
    html = gzip.decompress(base64.b64decode(page["html"])).decode("utf-8")
    row = results[page["id"]]
    other = trafilatura.extract(html, url=page["final_url"], include_comments=False, include_tables=False) or ""
    marked = structured(html)
    e3 = marked if len(other) < 0.5 * len(marked) else other
    best = max(row["marked"], row["sizes"]["E2"], row["sizes"]["E0"], len(e3))
    sizes[page["source"]].append((len(e3) < 0.5 * best, row["site_texts"]))
    if page["id"] in gold:
        found = blocks(html)
        reference = "\n".join(found[n] for a, b in gold[page["id"]] for n in range(a, b + 1))
        one = {
            "source": page["source"], "title": page["title"][:50], "ref": len(reference),
            "E0": row["coverage"]["E0"], "E2": row["coverage"]["E2"],
            "E3": round(coverage(reference, e3), 3), "dirtyE0": row["pollution"]["E0"],
            "dirtyE2": row["pollution"]["E2"], "dirtyE3": round(pollution(reference, e3), 3),
            "sE0": row["sizes"]["E0"], "sE2": row["sizes"]["E2"], "marked": row["marked"], "best": best,
        }
        rows.append(one)
print("marker against the reference, E0: under half by reference / by marker / both")
by_ref = [r for r in rows if r["E0"] < 0.5]
by_mark = [r for r in rows if r["sE0"] < 0.5 * max(r["marked"], r["sE2"], r["sE0"])]
print(len(by_ref), len(by_mark), len([r for r in by_ref if r in by_mark]))
print(f"E3: coverage median {median(r['E3'] for r in rows):.1%}, under half {sum(r['E3'] < .5 for r in rows) / len(rows):.1%},"
      f" pollution median {median(r['dirtyE3'] for r in rows):.1%}, worse than E0 {sum(r['E0'] - r['E3'] > .2 for r in rows) / len(rows):.1%}")
total = sum(v[0][1] for v in sizes.values())
weighted = sum(sum(x[0] for x in v) / len(v) * v[0][1] / total for v in sizes.values())
print(f"E3 weighted under half {weighted:.1%}; by site:", {s[:12]: f"{sum(x[0] for x in v) / len(v):.0%}" for s, v in sorted(sizes.items())})
print("\nlowest or worse pages")
for r in sorted(rows, key=lambda r: min(r["E0"], r["E2"], r["E3"])):
    if min(r["E0"], r["E2"], r["E3"]) < 0.7 or r["dirtyE2"] > 0.3:
        print(f"{r['source'][:12]:12} ref {r['ref']:5d} E0 {r['E0']:.2f}/{r['dirtyE0']:.2f} ({r['sE0']:5d}) E2 {r['E2']:.2f}/{r['dirtyE2']:.2f} ({r['sE2']:5d}) E3 {r['E3']:.2f}/{r['dirtyE3']:.2f} marked {r['marked']:5d} | {r['title'][:36]}")
