# SPDX-License-Identifier: AGPL-3.0-or-later
"""Memory of each container, sampled every second from its cgroup, until stopped (B09).

    python3 memwatch.py --project otlet --out results/mem.json &   # then kill -INT it

Memory is counted as `docker stats` does, without the reclaimable page cache (cgroup v2,
run as root). The summary gives, per container, the maximum
and mean in MiB, and the maximum of the sum over all containers of the project, which is the
"memory of the stack" of the spike criteria.
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

UNITS = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "kB": 1e3 / 2**20, "MB": 1e6 / 2**20, "GB": 1e9 / 2**20}


def running_containers(project: str) -> dict[str, Path]:
    """Name -> cgroup v2 directory of the running containers whose name starts with project."""
    output = subprocess.run(  # noqa: S603
        ["docker", "ps", "--no-trunc", "--format", "{{.ID}} {{.Names}}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    found = {}
    for line in output.splitlines():
        container_id, name = line.split(" ", 1)
        if name.startswith(project):
            found[name] = Path(f"/sys/fs/cgroup/system.slice/docker-{container_id}.scope")
    return found


def cgroup_memory_mib(cgroup: Path) -> float:
    """Memory used without the reclaimable page cache, computed as `docker stats` does
    (memory.current minus inactive_file)."""
    current = int((cgroup / "memory.current").read_text())
    inactive = 0
    for line in (cgroup / "memory.stat").read_text().splitlines():
        key, value = line.split()
        if key == "inactive_file":
            inactive = int(value)
    return (current - inactive) / 2**20


def to_mib(text: str) -> float:
    match = re.fullmatch(r"\s*([\d.]+)\s*([A-Za-z]+)\s*", text)
    if not match:
        raise ValueError(text)
    return float(match.group(1)) * UNITS[match.group(2)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="otlet", help="préfixe des noms de conteneurs")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    samples: dict[str, list[float]] = {}
    totals: list[float] = []
    started = datetime.now(UTC).isoformat(timespec="seconds")
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    containers = running_containers(args.project)
    while not stopping:
        total = 0.0
        for name, cgroup in containers.items():
            try:
                used = cgroup_memory_mib(cgroup)
            except OSError:
                continue
            samples.setdefault(name, []).append(used)
            total += used
        if total:
            totals.append(total)
        time.sleep(1)

    summary = {
        "started": started,
        "stopped": datetime.now(UTC).isoformat(timespec="seconds"),
        "samples": len(totals),
        "containers": {
            name: {"max_mib": round(max(v), 1), "mean_mib": round(sum(v) / len(v), 1)}
            for name, v in sorted(samples.items())
        },
        "stack_max_mib": round(max(totals), 1) if totals else None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
