# SPDX-License-Identifier: AGPL-3.0-or-later
"""S7.5: one series of 100 publications with injected faults on one configuration.

    python run_s7.py W1|W2|W3|G1 [--label NAME] [--count 100] [--results results]

docs/spikes/S7.md §3.4: the CMS is emptied, 50 publications out of 100 get a fault on their
first send (15 cut_before, 20 timeout_after, 15 cut_response, chosen by a fixed seed), the
others pass. At the end, the CMS is read directly (not through the proxy) to count duplicates
by key and by title. Writes results/s7-<label>-<time>.json.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cms import configurations
from connector import Publication, adapter, marker, publish

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "s3-document"))

from otlet_doc import render  # noqa: E402
from selfcheck import load  # noqa: E402

FAULTS = ["cut_before"] * 15 + ["timeout_after"] * 20 + ["cut_response"] * 15
SEED = 2026


def plan(count: int, seed: int) -> list[str | None]:
    rng = random.Random(seed)
    faults: list[str | None] = [*FAULTS[: count // 2 * len(FAULTS) // 50], *[None] * (count - count // 2 * len(FAULTS) // 50)]
    rng.shuffle(faults)
    return faults


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", choices=("W1", "W2", "W3", "G1"))
    parser.add_argument("--label")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--results", default=str(HERE / "results"))
    args = parser.parse_args()
    label = args.label or args.config

    direct = adapter(configurations()[args.config])
    proxied = adapter(configurations(proxy="http://s7-proxy")[args.config])
    expected = json.loads((HERE.parent / "s3-document" / "corpus" / "expected.json").read_text(encoding="utf-8"))
    documents = [(name, render.render(load(name))) for name in sorted(expected)]

    result: dict[str, Any] = {"config": args.config, "label": label, "started": datetime.now(UTC).isoformat(timespec="seconds"), "purged": direct.purge()}
    run = datetime.now(UTC).strftime("%H%M%S")
    publications = []
    for number, fault in enumerate(plan(args.count, SEED), start=1):
        name, html = documents[(number - 1) % len(documents)]
        publication = Publication(title=f"S7 {label} {run} n{number:03d} {name}", html=html)
        started = time.perf_counter()
        publish(proxied, publication, fault)
        publications.append((fault, publication, round(time.perf_counter() - started, 1)))
        print(f"{number:3d} {fault or '-':13s} {publication.state:10s} {publication.how or '':9s} resends={len(publication.resends)}", flush=True)

    time.sleep(20)  # let the held answers of timeout_after settle before counting
    inventory = [p for p in direct.inventory() if p["title"].startswith(f"S7 {label} {run} ")]
    by_title = collections.Counter(p["title"] for p in inventory)
    by_marker = collections.Counter(p["marker"] for p in inventory)
    keys = {marker(p.key): p for _, p, _ in publications}

    def blind(publication: Publication) -> bool:
        return any(not (len(r["lookups"]) == 2 and all(lookup == [] for lookup in r["lookups"])) for r in publication.resends)

    states = collections.Counter(p.state for _, p, _ in publications)
    result["summary"] = {
        "publications": len(publications),
        "faults": collections.Counter(f or "none" for f, _, _ in publications),
        "remote_posts": len(inventory),
        "duplicates_by_title": sum(n - 1 for n in by_title.values() if n > 1),
        "duplicates_by_key": sum(n - 1 for m, n in by_marker.items() if m in keys and n > 1),
        "missing": sum(1 for m in keys if by_marker[m] == 0 and keys[m].state == "published"),
        "states": states,
        "reconciled_automatically": round(states["published"] / len(publications), 4),
        "how": collections.Counter(p.how for _, p, _ in publications if p.how),
        "resends": sum(len(p.resends) for _, p, _ in publications),
        "blind_resends": sum(blind(p) for _, p, _ in publications),
        "by_fault": {
            fault: collections.Counter(p.state for f, p, _ in publications if (f or "none") == fault)
            for fault in ("none", "cut_before", "timeout_after", "cut_response")
        },
        "seconds_per_publication_max": max(s for _, _, s in publications),
    }
    result["publications"] = [
        {"title": p.title, "key": p.key, "fault": f, "state": p.state, "how": p.how, "remote_id": p.remote_id, "seconds": s, "events": p.events, "resends": p.resends}
        for f, p, s in publications
    ]
    out = Path(args.results)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"s7-{label}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    print(f"Result: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
