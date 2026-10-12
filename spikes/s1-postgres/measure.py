# SPDX-License-Identifier: AGPL-3.0-or-later
"""S1.4: one measurement pass of the five reads, with or without row-level security.

    python measure.py rls   --url postgresql+psycopg://otlet_app:…@db/otlet   --pass 1
    python measure.py norls --url postgresql+psycopg://otlet_bench:…@db/otlet --pass 1

"rls": application role, each read in a workspace transaction of otlet.platform.database
(the session factory of the product). "norls": a role with BYPASSRLS, same queries, plain
transaction. Protocol: docs/spikes/S1.md §3.4. Writes results/<variant>-pass<n>-<time>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "bench"))

from bench import Bench, write_result  # noqa: E402
from reads import reads  # noqa: E402

from otlet.platform import database  # noqa: E402

CLIENTS, EXECUTIONS, WARMUP_SECONDS = 4, 500, 30
if "--smoke" in sys.argv:  # functional trial on a reduced data set, never a measure
    sys.argv.remove("--smoke")
    EXECUTIONS, WARMUP_SECONDS = 20, 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=("rls", "norls"))
    parser.add_argument("--url", required=True)
    parser.add_argument("--pass", dest="number", type=int, required=True)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    manifest = json.loads((HERE / "data" / "manifest.json").read_text(encoding="utf-8"))
    workspace = uuid.UUID(manifest["measured_workspace"])
    engine = database.create_engine(args.url, pool_size=CLIENTS, max_overflow=0)

    def wrap(read):  # type: ignore[no-untyped-def]
        if args.variant == "rls":

            def run(rng):  # type: ignore[no-untyped-def]
                with database.workspace_transaction(engine, workspace) as connection:
                    return read(connection, rng)
        else:

            def run(rng):  # type: ignore[no-untyped-def]
                with engine.begin() as connection:
                    return read(connection, rng)

        return run

    workloads = {name: wrap(read) for name, read in reads(manifest).items()}
    bench = Bench(clients=CLIENTS, warmup_seconds=WARMUP_SECONDS, seed=args.seed + args.number)
    result = bench.run(workloads, EXECUTIONS)
    result.update(variant=args.variant, pass_number=args.number, dataset_seed=manifest["seed"])
    path = write_result(result, HERE / "results", f"{args.variant}-pass{args.number}")
    summary = {name: w["p95_ms"] for name, w in result["workloads"].items()}  # type: ignore[union-attr]
    print(json.dumps({"variant": args.variant, "pass": args.number, "p95_ms": summary}))
    print(f"Result: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
