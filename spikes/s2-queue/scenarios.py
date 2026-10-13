# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2: scenarios of docs/spikes/S2.md §3.2 to §3.5, for the engine named by S2_ENGINE.

    python scenarios.py setup            fresh database otlet_s2, roles, schemas
    python scenarios.py c1               100 rollbacks + 100 commits (transactional enqueue)
    python scenarios.py c2-enqueue       1 000 tasks with idempotency keys
    python scenarios.py c2-check         losses, double effects, resume delays (after the kills)
    python scenarios.py c5               100 tasks in 60 s, 10 cancelled; waits, then checks
    python scenarios.py c6-enqueue       200 tasks on two workspaces + 20 witnesses
    python scenarios.py c6-check         leaks between workspaces, witnesses

Each check writes results/<scenario>-<engine>-<time>.json and prints a summary.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import sqlalchemy as sa

import common
import engine
from otlet.platform import database, roles

HERE = Path(__file__).parent
RESULTS = HERE / "results"
SEED = 2026


def write(name: str, result: dict[str, object]) -> None:
    result["engine"] = engine.NAME
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    label = os.environ.get("S2_LABEL", "")
    result["label"] = label or "protocol"
    path = RESULTS / f"{name}{'-' + label if label else ''}-{engine.NAME}-{stamp}.json"
    path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, default=str))
    print(f"Result: {path}")


def scalar(query: str, **params: object) -> object:
    with common.admin_engine().connect() as connection:
        return connection.execute(sa.text(query), params).scalar()


def setup() -> None:
    with psycopg.connect(common.env("S2_SERVER_URL"), autocommit=True) as connection:
        connection.execute("DROP DATABASE IF EXISTS otlet_s2 WITH (FORCE)")
        connection.execute("CREATE DATABASE otlet_s2")
    migrator = psycopg.conninfo.conninfo_to_dict(common.env("S2_MIGRATOR_URL"))
    app = psycopg.conninfo.conninfo_to_dict(common.env("S2_APP_URL"))
    roles.provision(common.env("S2_ADMIN_URL"), str(migrator["password"]), str(app["password"]))
    common.apply_bench_schema()
    engine.apply_schema()
    print(f"otlet_s2 ready for {engine.NAME}")


def c1() -> None:
    rng = random.Random(SEED)

    def trial(commit: bool, index: int) -> None:
        workspace = rng.choice(common.WORKSPACES)
        ref = f"c1-{'commit' if commit else 'rollback'}-{index:03d}"
        with common.app_engine().connect() as connection:
            transaction = connection.begin()
            connection.execute(
                sa.text("SELECT set_config(:n, :v, true)"),
                {"n": database.WORKSPACE_SETTING, "v": str(workspace)},
            )
            connection.execute(
                sa.text("INSERT INTO notes (workspace_id, body) VALUES (:w, :b)"),
                {"w": workspace, "b": ref},
            )
            engine.defer("effect", ref, str(workspace), connection=connection)
            if commit:
                transaction.commit()
            else:
                transaction.rollback()

    with engine.opened():
        for index in range(100):
            trial(commit=False, index=index)
        for index in range(100):
            trial(commit=True, index=index)

    count_jobs = engine.count_jobs_query()
    count_notes = "SELECT count(*) FROM notes WHERE body LIKE :p"
    result: dict[str, object] = {
        "criterion": "C1",
        "rolled_back_trials": 100,
        "jobs_after_rollback": scalar(count_jobs, p="c1-rollback-%"),
        "notes_after_rollback": scalar(count_notes, p="c1-rollback-%"),
        "committed_trials": 100,
        "jobs_after_commit": scalar(count_jobs, p="c1-commit-%"),
        "notes_after_commit": scalar(count_notes, p="c1-commit-%"),
    }
    result["passed"] = (
        result["jobs_after_rollback"] == 0
        and result["notes_after_rollback"] == 0
        and result["jobs_after_commit"] == 100
    )
    write("c1", result)


def c2_enqueue() -> None:
    with engine.opened():
        for index in range(1_000):
            engine.defer("effect", f"c2-{index:04d}", str(common.WORKSPACES[index % 2]))
    print("1000 tasks enqueued")


def c2_check() -> None:
    with common.admin_engine().connect() as connection:
        done = connection.execute(
            sa.text("SELECT count(*) FROM effects WHERE task_ref LIKE 'c2-%'")
        ).scalar()
        doubles = connection.execute(
            sa.text(
                "SELECT count(*) FROM (SELECT task_ref FROM effects WHERE task_ref LIKE 'c2-%'"
                " GROUP BY task_ref HAVING count(*) > 1) d"
            )
        ).scalar()
        jobs = dict(connection.execute(sa.text(engine.jobs_by_status_query())).all())
        attempts = connection.execute(
            sa.text("SELECT count(*) FROM attempts WHERE task_ref LIKE 'c2-%'")
        ).scalar()
        # Attempts started after the effect existed: the idempotency key did its job.
        neutralized = connection.execute(
            sa.text(
                "SELECT count(*) FROM attempts a JOIN effects e USING (task_ref)"
                " WHERE a.task_ref LIKE 'c2-%' AND a.started_at > e.done_at"
            )
        ).scalar()
        kills = connection.execute(sa.text("SELECT count(*) FROM kills")).scalar()
        # Resume delay: for each task with an attempt on a worker killed after that attempt
        # started and before the task's effect, time from that kill to the effect.
        delays = (
            connection.execute(
                sa.text(
                    "SELECT e.task_ref, extract(epoch FROM e.done_at - k.killed_at) AS seconds"
                    " FROM effects e"
                    " JOIN attempts a ON a.task_ref = e.task_ref"
                    " JOIN LATERAL (SELECT killed_at FROM kills k"
                    "   WHERE k.worker = a.worker AND k.killed_at > a.started_at"
                    "   ORDER BY k.killed_at LIMIT 1) k ON true"
                    " WHERE e.task_ref LIKE 'c2-%' AND k.killed_at < e.done_at"
                )
            )
            .mappings()
            .all()
        )
    worst = max((float(d["seconds"]) for d in delays), default=0.0)
    result: dict[str, object] = {
        "criterion": "C2 C3 C4",
        "tasks": 1000,
        "kills": kills,
        "attempts": attempts,
        "effects": done,
        "lost": 1000 - int(done or 0),
        "double_effects": doubles,
        "attempts_neutralized_by_key": neutralized,
        "interrupted_tasks": len({d["task_ref"] for d in delays}),
        "worst_resume_seconds": round(worst, 1),
        "jobs_by_status": jobs,
    }
    result["passed"] = result["lost"] == 0 and doubles == 0 and worst <= 300
    write("c2", result)


def c5() -> None:
    rng = random.Random(SEED + 5)
    with engine.opened():
        ids = [
            (ref, engine.defer("effect", ref, str(common.WORKSPACES[0]), delay=60))
            for ref in (f"c5-{index:03d}" for index in range(100))
        ]
        cancelled = rng.sample(ids, 10)
        outcomes = [engine.cancel(job_id) for _, job_id in cancelled]
    cancelled_refs = [ref for ref, _ in cancelled]
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if scalar("SELECT count(*) FROM effects WHERE task_ref LIKE 'c5-%'") == 90:
            break
        time.sleep(5)
    time.sleep(15)
    with common.admin_engine().connect() as connection:
        ran_cancelled = connection.execute(
            sa.text("SELECT count(*) FROM attempts WHERE task_ref = ANY(:r)"),
            {"r": cancelled_refs},
        ).scalar()
        others_done = connection.execute(
            sa.text(
                "SELECT count(*) FROM effects WHERE task_ref LIKE 'c5-%'"
                " AND NOT task_ref = ANY(:r)"
            ),
            {"r": cancelled_refs},
        ).scalar()
    result: dict[str, object] = {
        "criterion": "C5",
        "cancel_calls_succeeded": sum(1 for ok in outcomes if ok),
        "cancelled_that_ran": ran_cancelled,
        "others_done": others_done,
        "details": {"cancelled": cancelled_refs},
    }
    result["passed"] = ran_cancelled == 0 and others_done == 90
    write("c5", result)


def c6_enqueue() -> None:
    for workspace in common.WORKSPACES:
        with database.workspace_transaction(common.app_engine(), workspace) as connection:
            for index in range(5):
                connection.execute(
                    sa.text("INSERT INTO notes (workspace_id, body) VALUES (:w, :b)"),
                    {"w": workspace, "b": f"c6-note-{index}"},
                )
    with engine.opened():
        for index in range(200):
            workspace = str(common.WORKSPACES[index % 2])
            engine.defer("read_notes", f"c6-{index:03d}", workspace)
            if index % 10 == 9:
                engine.defer("probe", f"c6-probe-{index:03d}", workspace)
    print("220 tasks enqueued")


def c6_check() -> None:
    with common.admin_engine().connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT task_ref, workspace_id, seen_workspaces FROM effects"
                " WHERE task_ref LIKE 'c6-%'"
            )
        ).all()
        listening = connection.execute(
            sa.text(
                "SELECT count(*) FROM pg_stat_activity WHERE usename = 'otlet_app'"
                " AND query ILIKE 'LISTEN%'"
            )
        ).scalar()
    readers = [r for r in rows if not r.task_ref.startswith("c6-probe")]
    probes = [r for r in rows if r.task_ref.startswith("c6-probe")]
    leaks = [r.task_ref for r in readers if set(r.seen_workspaces) - {r.workspace_id}]
    blind = [r.task_ref for r in readers if not r.seen_workspaces]
    probe_leaks = [r.task_ref for r in probes if str(r.workspace_id).startswith("00000000")]
    result: dict[str, object] = {
        "criterion": "C6",
        "readers_done": len(readers),
        "readers_with_foreign_rows": len(leaks),
        "readers_seeing_nothing": len(blind),
        "witnesses_done": len(probes),
        "witnesses_seeing_rows_without_context": len(probe_leaks),
        "listen_connections_of_app_role": listening,
        "details": {"leaks": leaks, "probe_leaks": probe_leaks},
    }
    result["passed"] = (
        len(readers) == 200 and not leaks and not blind and len(probes) == 20 and not probe_leaks
    )
    write("c6", result)


COMMANDS = {
    "setup": setup,
    "c1": c1,
    "c2-enqueue": c2_enqueue,
    "c2-check": c2_check,
    "c5": c5,
    "c6-enqueue": c6_enqueue,
    "c6-check": c6_check,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    COMMANDS[sys.argv[1]]()
