# SPDX-License-Identifier: AGPL-3.0-or-later
"""Common measurement bench of the É0 spikes (B09).

Runs named workloads with a fixed number of concurrent clients, after a warm-up, and reports
latency percentiles per workload as JSON. Standard library only, so it runs anywhere Python
does; workloads that need a driver (psycopg…) import it themselves.

    from bench import Bench
    bench = Bench(clients=4, warmup_seconds=30, seed=1)
    result = bench.run({"health": lambda rng: urlopen(url).read()}, executions_per_workload=500)

Command line, for an HTTP endpoint:
    python bench.py http https://host/health --executions 500 --clients 4 --insecure
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import ssl
import statistics
import sys
import threading
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

Workload = Callable[[random.Random], object]


def percentile(sorted_values: list[float], fraction: float) -> float:
    """Nearest-rank percentile of an already sorted list."""
    if not sorted_values:
        return float("nan")
    rank = max(1, round(fraction * len(sorted_values) + 0.5))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def summarize(latencies_ms: list[float], errors: int) -> dict[str, float | int]:
    values = sorted(latencies_ms)
    return {
        "count": len(values),
        "errors": errors,
        "min_ms": round(values[0], 2) if values else float("nan"),
        "p50_ms": round(percentile(values, 0.50), 2),
        "p95_ms": round(percentile(values, 0.95), 2),
        "p99_ms": round(percentile(values, 0.99), 2),
        "max_ms": round(values[-1], 2) if values else float("nan"),
        "mean_ms": round(statistics.fmean(values), 2) if values else float("nan"),
    }


class Bench:
    def __init__(self, clients: int, warmup_seconds: float, seed: int) -> None:
        self.clients = clients
        self.warmup_seconds = warmup_seconds
        self.seed = seed

    def run(self, workloads: dict[str, Workload], executions_per_workload: int) -> dict[str, object]:
        """Warm up, then execute every workload `executions_per_workload` times, interleaved at
        random across `clients` threads. Returns per-workload latency summaries."""
        plan = [name for name in workloads for _ in range(executions_per_workload)]
        random.Random(self.seed).shuffle(plan)

        self._warm_up(workloads)

        latencies: dict[str, list[float]] = {name: [] for name in workloads}
        errors: dict[str, int] = dict.fromkeys(workloads, 0)
        lock = threading.Lock()
        cursor = iter(plan)

        def client(index: int) -> None:
            rng = random.Random(self.seed * 1000 + index)
            while True:
                with lock:
                    name = next(cursor, None)
                if name is None:
                    return
                start = time.perf_counter()
                try:
                    workloads[name](rng)
                except Exception as error:  # noqa: BLE001 (counted, then reported)
                    with lock:
                        errors[name] += 1
                    print(f"error in {name}: {error!r}", file=sys.stderr)
                    continue
                elapsed = (time.perf_counter() - start) * 1000
                with lock:
                    latencies[name].append(elapsed)

        started = datetime.now(UTC)
        wall = time.perf_counter()
        threads = [threading.Thread(target=client, args=(i,)) for i in range(self.clients)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return {
            "started": started.isoformat(timespec="seconds"),
            "duration_s": round(time.perf_counter() - wall, 2),
            "clients": self.clients,
            "warmup_s": self.warmup_seconds,
            "seed": self.seed,
            "executions_per_workload": executions_per_workload,
            "host": platform.node(),
            "workloads": {name: summarize(latencies[name], errors[name]) for name in workloads},
        }

    def _warm_up(self, workloads: dict[str, Workload]) -> None:
        rng = random.Random(self.seed - 1)
        deadline = time.monotonic() + self.warmup_seconds
        names = list(workloads)
        while time.monotonic() < deadline:
            try:
                workloads[rng.choice(names)](rng)
            except Exception:  # noqa: BLE001,S110 (warm-up only)
                pass


def write_result(result: dict[str, object], directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"{name}-{stamp}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    http = sub.add_parser("http", help="mesure d'une adresse HTTP(S) en GET")
    http.add_argument("url")
    http.add_argument("--executions", type=int, default=500)
    http.add_argument("--clients", type=int, default=4)
    http.add_argument("--warmup", type=float, default=5)
    http.add_argument("--seed", type=int, default=1)
    http.add_argument("--insecure", action="store_true", help="certificat non vérifié (autorité locale)")
    http.add_argument("--out", type=Path, default=Path(__file__).parent / "results")
    http.add_argument("--name", default="http")
    args = parser.parse_args()

    context = ssl._create_unverified_context() if args.insecure else None  # noqa: S323

    def get(_rng: random.Random) -> object:
        with urllib.request.urlopen(args.url, timeout=10, context=context) as response:  # noqa: S310
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            return response.read()

    result = Bench(args.clients, args.warmup, args.seed).run({"get": get}, args.executions)
    result["target"] = args.url
    path = write_result(result, args.out, args.name)
    print(json.dumps(result["workloads"], indent=2))
    print(f"Result: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
