# SPDX-License-Identifier: AGPL-3.0-or-later
"""TEXTE1b: docs/spikes/TEXTE1b.md §3. Three extractions of the frozen pages, compared with a
reference written by hand and with what each page holds. No model, no network, nothing written in
the Veille. Run by run-texte1b.sh, in the image of the worker with trafilatura beside it:

    python texte1b.py <folder>             results.jsonl, one line per page
    python texte1b.py <folder> --summary   the criteria
"""

import base64
import gzip
import json
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from statistics import median

SITES = ("Les Numériques", "RTBF Info", "Audiofanzine", "Futura Sciences")
FALLBACK_SHARE = 0.5
BODY_MIN = 200
LONG_PARAGRAPH = 80
EXTRACTORS = ("E0", "E1", "E2")
SHORT = 0.5
COVERAGE_MEDIAN = 0.90
UNDER_HALF_MAX = 0.05
POLLUTION_MEDIAN = 0.15
WORSE_MAX = 0.05
WORSE_BY = 0.20
SITE_SHORT_MAX = 0.05
P95_SECONDS = 0.3


def words(text: str) -> list[str]:
    bare = unicodedata.normalize("NFKD", text.casefold())
    bare = "".join(c for c in bare if unicodedata.category(c) not in ("Mn", "Cf"))
    return re.findall(r"\w+", bare)


def shingles(text: str) -> set[tuple[str, ...]]:
    found = words(text)
    return {tuple(found[n : n + 3]) for n in range(max(0, len(found) - 2))} or {tuple(found)}


def coverage(reference: str, text: str) -> float:
    want = shingles(reference)
    return len(want & shingles(text)) / len(want) if want else 1.0


def pollution(reference: str, text: str) -> float:
    got = shingles(text)
    return len(got - shingles(reference)) / len(got) if got and text.strip() else 0.0


def structured(html: str) -> str:
    """The article the page itself marks: articleBody, else the long paragraphs of its largest
    <article>."""
    import lxml.html

    from otlet.collection.adapters.parsing import clean_text

    bodies = []
    for found in re.findall(r'"articleBody"\s*:\s*"((?:[^"\\]|\\.)*)"', html):
        try:
            bodies.append(clean_text(json.loads(f'"{found}"')))
        except ValueError:
            continue
    best = max(bodies, key=len, default="")
    if len(best) >= BODY_MIN:
        return best
    tree = lxml.html.fromstring(html)
    articles = []
    for article in tree.iter("article"):
        kept = [" ".join(p.text_content().split()) for p in article.iter("p")]
        articles.append("\n\n".join(p for p in kept if len(p) > LONG_PARAGRAPH))
    return max(articles, key=len, default="")


def extract_all(html: str, url: str) -> dict[str, tuple[str, float]]:
    import trafilatura

    from otlet.collection.adapters.parsing import ReadabilityReader

    began = time.perf_counter()
    page = ReadabilityReader().extract(html, url)
    first = page.text if page else ""
    e0 = time.perf_counter() - began
    began = time.perf_counter()
    marked = structured(html)
    fallback = marked if len(first) < FALLBACK_SHARE * len(marked) else first
    e1 = e0 + time.perf_counter() - began
    began = time.perf_counter()
    other = trafilatura.extract(html, url=url, include_comments=False, include_tables=False) or ""
    e2 = time.perf_counter() - began
    return {"E0": (first, e0), "E1": (fallback, e1), "E2": (other, e2)}


def run(folder: Path, scripts: Path) -> None:
    sys.path.insert(0, str(scripts))
    from gold_blocks import blocks

    gold = json.loads((scripts / "gold.json").read_text(encoding="utf-8"))
    with (folder / "results.jsonl").open("w", encoding="utf-8") as out:
        for line in (folder / "pages.jsonl").open(encoding="utf-8"):
            page = json.loads(line)
            if page.get("status") != 200 or not page.get("html"):
                continue
            html = gzip.decompress(base64.b64decode(page["html"])).decode("utf-8")
            texts = extract_all(html, page["final_url"])
            row = {
                "id": page["id"], "source": page["source"], "site_texts": page["site_texts"],
                "sizes": {k: len(v[0]) for k, v in texts.items()},
                "seconds": {k: round(v[1], 3) for k, v in texts.items()},
                "marked": len(structured(html)),
            }
            if page["id"] in gold:
                found = blocks(html)
                reference = "\n".join(
                    found[n] for a, b in gold[page["id"]] for n in range(a, b + 1)
                )
                row["reference"] = len(reference)
                row["coverage"] = {k: round(coverage(reference, v[0]), 3) for k, v in texts.items()}
                row["pollution"] = {k: round(pollution(reference, v[0]), 3) for k, v in texts.items()}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")


def summary(folder: Path) -> None:
    rows = [json.loads(line) for line in (folder / "results.jsonl").open(encoding="utf-8")]
    gold = [r for r in rows if "coverage" in r]
    print(f"{len(rows)} pages, {len(gold)} with the reference")
    for name in EXTRACTORS:
        cover = [r["coverage"][name] for r in gold]
        dirty = [r["pollution"][name] for r in gold]
        under = sum(c < SHORT for c in cover) / len(cover)
        worse = sum(r["coverage"]["E0"] - r["coverage"][name] > WORSE_BY for r in gold) / len(gold)
        seconds = sorted(r["seconds"][name] for r in rows)
        p95 = seconds[int(0.95 * len(seconds))]
        met = (
            median(cover) >= COVERAGE_MEDIAN and under <= UNDER_HALF_MAX
            and median(dirty) <= POLLUTION_MEDIAN and worse <= WORSE_MAX and p95 <= P95_SECONDS
        )
        print(
            f"{name}: coverage median {median(cover):.1%}, under half {under:.1%},"
            f" pollution median {median(dirty):.1%}, worse than E0 {worse:.1%},"
            f" p95 {p95 * 1000:.0f} ms, gold criteria met: {met}"
        )
    # The proportion: E0 against the longest of what the page marks and what E2 finds.
    sites = defaultdict(list)
    for row in rows:
        best = max(row["marked"], row["sizes"]["E2"], row["sizes"]["E0"])
        sites[row["source"]].append(row)
        row["best"] = best
    total = sum(group[0]["site_texts"] for group in sites.values())
    print("\nsite, texts, sampled; under half of the longest, by extraction")
    weighted = dict.fromkeys(EXTRACTORS, 0.0)
    for source, group in sorted(sites.items(), key=lambda kv: kv[0]):
        shares = {
            name: sum(r["sizes"][name] < SHORT * r["best"] for r in group) / len(group)
            for name in EXTRACTORS
        }
        for name in EXTRACTORS:
            weighted[name] += shares[name] * group[0]["site_texts"] / total
        cells = " ".join(f"{name} {shares[name]:.0%}" for name in EXTRACTORS)
        print(f"  {source[:24]:24} {group[0]['site_texts']:5d} {len(group):3d}  {cells}")
    print("weighted by site:", " ".join(f"{k} {v:.1%}" for k, v in weighted.items()))
    for name in EXTRACTORS:
        worst = max(
            sum(r["sizes"][name] < SHORT * r["best"] for r in sites[s]) / len(sites[s])
            for s in SITES
        )
        print(f"{name}: worst of the 4 sites {worst:.0%}, met: {worst <= SITE_SHORT_MAX}")


if __name__ == "__main__":
    # After the libraries of the image, so that E0 runs on the versions of the product.
    sys.path.append(os.environ.get("TEXTE1B_EXTRA", ""))
    where = Path(sys.argv[1])
    if "--summary" in sys.argv:
        summary(where)
    else:
        run(where, Path(__file__).parent)
