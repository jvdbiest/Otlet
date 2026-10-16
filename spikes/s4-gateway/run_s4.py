# SPDX-License-Identifier: AGPL-3.0-or-later
"""S4.4, S4.5: the measures of docs/spikes/S4.md §3.3 to §3.5.

    python run_s4.py briefs <provider>     50 briefs, one repair at most (C1)
    python run_s4.py budget                200 concurrent calls on fake-a (C2)
    python run_s4.py fallbacks             100 seeded error scenarios (C3)
    python run_s4.py conformity            one call per adapter on the test providers

Environment: S4_PROVIDERS (JSON, provider -> base URL), S4_DATABASE_URL, S4_FAKE (base URL
of the fake provider controls, without port). Writes results/s4-<measure>-<time>.json.
"""

from __future__ import annotations

import collections
import json
import os
import random
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import draft
import gateway
from budget import Budget, new_scope

HERE = Path(__file__).parent


def write(measure: str, result: dict[str, Any]) -> None:
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    path = out / f"s4-{measure}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.get("summary", {}), ensure_ascii=False))
    print(f"Result: {path}")


def control(port: int, queue: list[str]) -> None:
    request = urllib.request.Request(f"{os.environ['S4_FAKE']}:{port}/control", data=json.dumps({"queue": queue}).encode(), method="POST")
    urllib.request.urlopen(request, timeout=10).read()  # noqa: S310 (test network)


def briefs(provider: str) -> None:
    rows = []
    for brief in draft.briefs():
        started = time.perf_counter()
        outcome = gateway.generate(brief, [provider])
        rows.append({
            "brief": brief.number, "language": brief.language, "valid": outcome.draft is not None,
            "repaired": outcome.repaired, "error": outcome.error, "seconds": round(time.perf_counter() - started, 1),
            "tokens_out": sum(c.get("tokens_out", 0) for c in outcome.calls), "calls": outcome.calls,
            "draft": outcome.draft.model_dump() if outcome.draft else None,
        })
        print(f"{brief.number:2d} valid={outcome.draft is not None} repaired={outcome.repaired} {rows[-1]['seconds']} s {outcome.error or ''}"[:200], flush=True)
    valid = [r for r in rows if r["valid"]]
    summary = {
        "provider": provider, "model": gateway.entry(provider)["model"], "briefs": len(rows),
        "valid_without_repair": round(sum(1 for r in valid if not r["repaired"]) / len(rows), 4),
        "valid_after_one_repair": round(len(valid) / len(rows), 4),
        "errors": collections.Counter((r["error"] or "").split(":")[0] for r in rows if not r["valid"]),
        "seconds_median": sorted(r["seconds"] for r in rows)[len(rows) // 2],
        "seconds_max": max(r["seconds"] for r in rows),
        "tokens_out_median": sorted(r["tokens_out"] for r in rows)[len(rows) // 2],
    }
    write(f"briefs-{provider.replace(':', '-')}", {"summary": summary, "rows": rows})


def budget() -> None:
    scope, limit = new_scope(), 1.00
    ledger = Budget(scope)
    ledger.create(limit)
    all_briefs = draft.briefs()
    demand = sum(gateway.estimate_cost("fake-a", draft.prompt(all_briefs[i % 50])) for i in range(200))

    def one(i: int) -> str | None:
        return gateway.generate(all_briefs[i % 50], ["fake-a"], ledger).error

    control(8001, [])
    with ThreadPoolExecutor(max_workers=50) as pool:
        errors = list(pool.map(one, range(200)))
    state = ledger.state()
    summary = {
        "calls": 200, "limit": limit, "estimated_demand": round(demand, 4),
        "succeeded": sum(e is None for e in errors), "refused_for_budget": sum(e == "budget" for e in errors),
        "other_errors": collections.Counter(e for e in errors if e not in (None, "budget")),
        "spent": round(state["spent"], 6), "reserved_left": round(state["reserved"], 6),
        "peak_committed": round(state["peak_committed"], 6), "never_exceeded": state["peak_committed"] <= limit and state["spent"] <= limit,
    }
    write("budget", {"summary": summary, "scope": scope})


SCENARIOS = {
    "429_short": (25, ["429:1", "ok"], [("fake-a", "quota"), ("fake-a", None)], "fake-a", None),
    "429_repeated": (15, ["429:1", "429:1", "429:1"], [("fake-a", "quota")] * 3 + [("fake-b", None)], "fake-b", None),
    "5xx_once": (25, ["500", "ok"], [("fake-a", "unavailable"), ("fake-a", None)], "fake-a", None),
    "5xx_repeated": (15, ["500", "500"], [("fake-a", "unavailable")] * 2 + [("fake-b", None)], "fake-b", None),
    "400": (10, ["400"], [("fake-a", "refused")], None, "refused"),
    "timeout": (10, ["timeout", "timeout"], [("fake-a", "unavailable")] * 2 + [("fake-b", None)], "fake-b", None),
}


def fallbacks() -> None:
    gateway.TIMEOUT_SECONDS = 3.0  # the fake provider sleeps 6 s on "timeout"
    plan = [name for name, (count, *_rest) in SCENARIOS.items() for _ in range(count)]
    random.Random(2026).shuffle(plan)
    brief = draft.briefs()[0]
    rows = []
    for number, name in enumerate(plan, start=1):
        _count, queue, expected_calls, expected_provider, expected_error = SCENARIOS[name]
        control(8001, queue)
        control(8002, [])
        ledger = Budget(new_scope())
        ledger.create(100.0)
        outcome = gateway.generate(brief, ["fake-a", "fake-b"], ledger)
        calls = [(c["provider"], c.get("error")) for c in outcome.calls]
        state = ledger.state()
        error_kind = outcome.error.split(":")[0] if outcome.error else None
        correct = calls == expected_calls and outcome.provider == expected_provider and error_kind == expected_error and abs(state["reserved"]) < 1e-9
        rows.append({"scenario": name, "correct": correct, "calls": calls, "provider": outcome.provider, "error": outcome.error, "reserved_left": state["reserved"]})
        print(f"{number:3d} {name:13s} {'ok' if correct else 'WRONG'} {calls}", flush=True)
    summary = {
        "scenarios": len(rows), "correct": sum(r["correct"] for r in rows),
        "by_scenario": {n: f"{sum(r['correct'] for r in rows if r['scenario'] == n)}/{sum(1 for r in rows if r['scenario'] == n)}" for n in SCENARIOS},
    }
    write("fallbacks", {"summary": summary, "rows": rows})


def conformity() -> None:
    brief = draft.briefs()[0]
    rows = {}
    for provider in ("fake-a", "fake-anthropic"):
        outcome = gateway.generate(brief, [provider])
        rows[provider] = {"valid": outcome.draft is not None, "error": outcome.error, "calls": outcome.calls}
    blocked = gateway.generate(brief, ["anthropic"])
    rows["anthropic (blocked)"] = {"valid": blocked.draft is not None, "error": blocked.error}
    write("conformity", {"summary": {k: v["valid"] if v["error"] is None else v["error"] for k, v in rows.items()}, "rows": rows})


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "briefs":
        briefs(sys.argv[2])
    elif command == "budget":
        budget()
    elif command == "fallbacks":
        fallbacks()
    elif command == "conformity":
        conformity()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
