# SPDX-License-Identifier: AGPL-3.0-or-later
"""TEXTE1b: the blocks of 4 frozen pages per site, in the order of the page, without any extractor:
what the reference is written from, by hand (gold.json). Needs lxml: in the worker container, or
any Python with it. Usage: python gold_blocks.py pages.jsonl [--list]"""

import base64
import gzip
import json
import random
import sys
from collections import defaultdict

import lxml.html

BLOCKS = ("p", "h1", "h2", "h3", "li", "blockquote")
MIN_CHARS = 30
PER_SITE = 4


def blocks(html: str) -> list[str]:
    tree = lxml.html.fromstring(html)
    for bad in tree.xpath("//script|//style|//noscript|//template"):
        bad.drop_tree()
    out = []
    for element in tree.iter(*BLOCKS):
        # A block inside another block is read with it.
        if any(parent.tag in BLOCKS for parent in element.iterancestors()):
            continue
        text = " ".join(element.text_content().split())
        if len(text) >= MIN_CHARS:
            out.append(text)
    return out


def chosen(path: str) -> list[dict]:
    pages = defaultdict(list)
    for line in open(path, encoding="utf-8"):
        page = json.loads(line)
        if page.get("html") and page.get("status") == 200:
            pages[page["source"]].append(page)
    pick = random.Random(1101)
    out = []
    for source in sorted(pages):
        ordered = sorted(pages[source], key=lambda p: p["id"])
        out += pick.sample(ordered, min(PER_SITE, len(ordered)))
    return out


if __name__ == "__main__":
    for page in chosen(sys.argv[1]):
        html = gzip.decompress(base64.b64decode(page["html"])).decode("utf-8")
        found = blocks(html)
        print(f"\n### {page['id']} | {page['source']} | {page['title'][:90]}")
        print(f"resume: {(page['summary'] or '')[:90]}")
        for n, text in enumerate(found[:70]):
            print(f"{n}: {text[:58]}")
        if len(found) > 70:
            print(f"… {len(found)} blocks")
