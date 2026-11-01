# SPDX-License-Identifier: AGPL-3.0-or-later
"""ADR-0047: the reader of the product, with its filter of hidden elements and the version the lock
gives, on the frozen pages of TEXTE1c and TEXTE1b, against their references and E3 of the bench.
A check, not a new measure. In the image, without network: python recheck_product.py <dir> <gold>"""

import base64
import gzip
import importlib.metadata
import json
import resource
import sys
import time
from pathlib import Path
from statistics import median

sys.path.insert(0, "/scripts")
from gold_blocks import blocks  # noqa: E402
from texte1c import coverage, pollution  # noqa: E402

from otlet.collection.adapters.parsing import ArticleReader  # noqa: E402

print("trafilatura", importlib.metadata.version("trafilatura"))
folder, gold = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
results = {}
for line in (folder / "results.jsonl").open(encoding="utf-8"):
    row = json.loads(line)
    results[row["id"]] = row
reader, rows, seconds, empty, moved = ArticleReader(), [], [], 0, 0
for line in (folder / "pages.jsonl").open(encoding="utf-8"):
    page = json.loads(line)
    if page.get("status") != 200 or not page.get("html"):
        continue
    html = gzip.decompress(base64.b64decode(page["html"])).decode("utf-8")
    began = time.perf_counter()
    read = reader.extract(html, page["final_url"])
    seconds.append(time.perf_counter() - began)
    text = read.text if read else ""
    empty += not text
    before = results[page["id"]]["sizes"]["E3"]
    moved += abs(len(text) - before) > 0.2 * max(before, 1)
    if page["id"] in gold:
        found = blocks(html)
        reference = "\n".join(found[n] for a, b in gold[page["id"]] for n in range(a, b + 1))
        rows.append((
            coverage(reference, text), pollution(reference, text), results[page["id"]]["coverage"]["E0"],
            page["source"], page["title"][:50],
        ))
seconds.sort()
print(f"{len(seconds)} pages, empty {empty}, more than 20 % from E3 of the bench {moved}, p95 {seconds[int(.95 * len(seconds))] * 1000:.0f} ms")
print(f"coverage median {median(r[0] for r in rows):.1%}, under half {sum(r[0] < .5 for r in rows) / len(rows):.1%},"
      f" pollution median {median(r[1] for r in rows):.1%}, worse than E0 {sum(r[2] - r[0] > .2 for r in rows) / len(rows):.1%}")
for r in rows:
    if r[0] < .7:
        print(f"  {r[0]:.2f} (E0 {r[2]:.2f}) {r[3][:14]} | {r[4]}")
print("peak MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)
