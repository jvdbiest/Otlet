# SPDX-License-Identifier: AGPL-3.0-or-later
"""P01: one measurement pass of the search of the product (docs/spikes/P01.md §3.2 to §3.4).

    python measure.py --url postgresql+psycopg://otlet_app:…@db/otlet --pass 1 [--smoke]
    python measure.py --url … --selectivity
    python measure.py --url … --explain --admin-url postgresql://postgres:…@db/otlet

Each search goes through otlet.watch.adapters.postgres.PostgresWatchStore.search, which opens
the workspace transaction of the product (forced row-level security) and returns 50 results.
Writes results/pass<n>-<time>.json, results/selectivity.json, or results/explain.txt: the plan
of the text match of `search_candidates`, under its own role (ADR-0033), for the first query
of each family.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "bench"))

import sqlalchemy as sa  # noqa: E402
from bench import Bench, write_result  # noqa: E402

from otlet.collection.domain.model import SEARCH_CONFIGS, SIMPLE_SEARCH  # noqa: E402
from otlet.platform import database  # noqa: E402
from otlet.watch.adapters.postgres import PostgresWatchStore  # noqa: E402

CLIENTS, EXECUTIONS, WARMUP_SECONDS = 4, 500, 30
RESULTS = 50


def selectivity(engine: sa.Engine, workspace: uuid.UUID, families: dict[str, list[str]]) -> int:
    """The share of the items of the workspace that each query matches (information only)."""
    report: dict[str, object] = {}
    with database.workspace_transaction(engine, workspace) as connection:
        total = connection.execute(sa.text("SELECT count(*) FROM source_items")).scalar_one()
        for family, queries in families.items():
            shares = [
                connection.execute(
                    # The items that match, in every language configuration (ADR-0033).
                    sa.text("SELECT count(*) FROM search_candidates(:q, NULL)"),
                    {"q": query},
                ).scalar_one()
                / total
                for query in queries
            ]
            report[family] = {
                "median_share": round(statistics.median(shares), 4),
                "max_share": round(max(shares), 4),
                "queries_over_10_percent": sum(1 for s in shares if s > 0.10),
            }
    report["items_in_workspace"] = total
    out = HERE / "results" / "selectivity.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


def explain(admin_url: str, workspace: uuid.UUID, families: dict[str, list[str]]) -> int:
    """The plan of the body of search_candidates (migration 0012), run as otlet_search."""
    configs = (*dict.fromkeys(SEARCH_CONFIGS.values()), SIMPLE_SEARCH)
    matches = " OR ".join(
        f"i.search @@ websearch_to_tsquery('{config}'::regconfig, :q)" for config in configs
    )
    body = (
        "EXPLAIN (ANALYZE, BUFFERS) SELECT i.id FROM source_items AS i"  # noqa: S608
        f" WHERE i.workspace_id = :w AND ({matches})"
    )
    lines = []
    engine = database.create_engine(admin_url)
    with engine.begin() as connection:
        connection.execute(sa.text("SET LOCAL ROLE otlet_search"))
        for family, queries in families.items():
            plan = connection.execute(sa.text(body), {"w": workspace, "q": queries[0]}).scalars()
            lines += [f"=== {family}: {queries[0]!r}", *plan, ""]
    out = HERE / "results" / "explain.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Plans: {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--pass", dest="number", type=int, default=0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--smoke", action="store_true", help="20 executions, never a measure")
    parser.add_argument("--selectivity", action="store_true")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--admin-url", help="for --explain: a superuser connection")
    args = parser.parse_args()

    manifest = json.loads((HERE / "data" / "manifest.json").read_text(encoding="utf-8"))
    families = json.loads((HERE / "data" / "queries.json").read_text(encoding="utf-8"))
    workspace = uuid.UUID(manifest["measured_workspace"])
    engine = database.create_engine(args.url, pool_size=CLIENTS, max_overflow=0)
    if args.selectivity:
        return selectivity(engine, workspace, families)
    if args.explain:
        return explain(args.admin_url, workspace, families)

    store = PostgresWatchStore(engine, lambda connection, name, **kwargs: 0)

    def workload(queries: list[str]):  # type: ignore[no-untyped-def]
        def run(rng: random.Random) -> object:
            return store.search(workspace, rng.choice(queries), RESULTS)

        return run

    executions, warmup = (20, 1) if args.smoke else (EXECUTIONS, WARMUP_SECONDS)
    bench = Bench(clients=CLIENTS, warmup_seconds=warmup, seed=args.seed + args.number)
    result = bench.run({name: workload(q) for name, q in families.items()}, executions)
    result.update(pass_number=args.number, items=manifest["items"], smoke=args.smoke)
    name = f"smoke-pass{args.number}" if args.smoke else f"pass{args.number}"
    path = write_result(result, HERE / "results", name)
    workloads = result["workloads"]
    summary = {name: w["p95_ms"] for name, w in workloads.items()}  # type: ignore[union-attr]
    print(json.dumps({"pass": args.number, "p95_ms": summary}, ensure_ascii=False))
    print(f"Result: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
