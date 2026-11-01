# SPDX-License-Identifier: AGPL-3.0-or-later
"""TEXTE1c, after the conclusion: why does Les Numériques stay under the criterion? What E0 holds
beyond E3 on those pages. Reading only, outside the protocol."""

import base64
import gzip
import json
import os
import re
import sys
from pathlib import Path

sys.path.append(os.environ.get("TEXTE1C_EXTRA", ""))
sys.path.insert(0, "/scripts")
from texte1c import extract_all  # noqa: E402

folder = Path(sys.argv[1])
results = {}
for line in (folder / "results.jsonl").open(encoding="utf-8"):
    row = json.loads(line)
    results[row["id"]] = row
for row in results.values():
    if "coverage" in row:
        print(f"{row['source'][:14]:14} cover E0 {row['coverage']['E0']:.2f} E3 {row['coverage']['E3']:.2f} dirty E0 {row['pollution']['E0']:.2f} E3 {row['pollution']['E3']:.2f} ref {row['reference']:5d} sizes {row['sizes']}")
print()
for line in (folder / "pages.jsonl").open(encoding="utf-8"):
    page = json.loads(line)
    if page.get("source") != "Les Numériques" or not page.get("html"):
        continue
    row = results[page["id"]]
    best = max(row["marked"], row["sizes"]["E2"], row["sizes"]["E0"])
    if row["sizes"]["E3"] >= 0.5 * best:
        continue
    html = gzip.decompress(base64.b64decode(page["html"])).decode("utf-8")
    texts = extract_all(html, page["final_url"])
    e0, e3 = texts["E0"][0], texts["E3"][0]
    prices = len(re.findall(r"\d[\d ]*,\d\d €", e0))
    print(f"{page['title'][:60]} | E0 {len(e0)} ({prices} prix) E3 {len(e3)} marked {row['marked']}")
    print(f"   E3: {e3[:110]!r}")
    print(f"   E0 milieu: {e0[len(e0) // 2 : len(e0) // 2 + 90]!r}")
