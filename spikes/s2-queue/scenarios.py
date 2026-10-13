# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2: scenarios of docs/spikes/S2.md §3.2 to §3.5, for Procrastinate.

    python scenarios.py setup            fresh database otlet_s2, roles, schemas
    python scenarios.py c1               100 rollbacks + 100 commits (transactional enqueue)
    python scenarios.py c2-enqueue       1 000 tasks with idempotency keys
    python scenarios.py c2-check         losses, double effects, resume delays (after the kills)
    python scenarios.py c5               100 tasks in 60 s, 10 cancelled; waits, then checks
    python scenarios.py c6-enqueue       200 tasks on two workspaces + 20 witnesses
    python scenarios.py c6-check         leaks between workspaces, witnesses

Each check writes results/<scenario>-<time>.json and prints a summary.
"""

from __future__ import annotations

import json
import random
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import sqlalchemy as sa

import common
from otlet.platform import database, roles

HERE = Path(__file__).parent
RESULTS = HERE / "results"
SEED = 2026


def write(name: str, result: dict[str, object]) -> None:
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS / f"{name}-{stamp}.json"
    path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, default=str))
    print(f"Result: {path}")


def scalar(query: str, **params: object) -> object:
    with common.admin_engine().connect() as connection:
        return connection.execute(sa.text(query), params).scalar()


def setup() -> None:
    server_url = common.env("S2_SERVER_URL")  # superuser on the maintenance database
    with psycopg.connect(server_url, autocommit=True) as connection:
        connection.execute("DROP DATABASE IF EXISTS otlet_s2 WITH (FORCE)")
        connection.execute("CREATE DATABASE otlet_s2")
    migrator = psycopg.conninfo.conninfo_to_dict(common.env("S2_MIGRATOR_URL"))
    app = psycopg.conninfo.conninfo_to_dict(common.env("S2_APP_URL"))
    roles.provision(common.env("S2_ADMIN_URL"), str(migrator["password"]), str(app["password"]))
    import procrastinate_app

    procrastinate_app.apply_schema()
    common.apply_bench_schema()
    print("otlet_s2 ready")


def c1() -> None:
    import procrastinate_app

    engine = common.app_engine()
    rng = random.Random(SEED)

    def trial(commit: bool) -> None:
        workspace = rng.choice(common.WORKSPACES)
        marker = f"c1-{'commit' if commit else 'rollback'}-{uuid.uuid4()}"
        connection = engine.connect()
        transaction = connection.begin()
        connection.execute(
            sa.text("SELECT set_config(:n, :v, true)"),
            {"n": database.WORKSPACE_SETTING, "v": str(workspace)},
        )
        connection.execute(
            sa.text("INSERT INTO notes (workspace_id, body) VALUES (:w, :b)"),
            {"w": workspace, "b": marker},
        )
        driver = connection.connection.driver_connection
        procrastinate_app.effect.configure(connection=driver).defer(
            key=marker, workspace=str(workspace), ref=marker
        )
        if commit:
            transaction.commit()
        else:
            transaction.rollback()
        connection.close()

    with procrastinate_app.app.open():
        for _ in range(100):
            trial(commit=False)
        for _ in range(100):
            trial(commit=True)

    count_jobs = "SELECT count(*) FROM procrastinate_jobs WHERE args->>'ref' LIKE :p"
    count_notes = "SELECT count(*) FROM notes WHERE body LIKE :p"
    result = {
        "criterion": "C1",
        "engine": "procrastinate",
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
    write("c1-procrastinate", result)


def c2_enqueue() -> None:
    import procrastinate_app

    with procrastinate_app.app.open():
        for index in range(1_000):
            workspace = common.WORKSPACES[index % 2]
            ref = f"c2-{index:04d}"
            procrastinate_app.effect.defer(key=f"key-{ref}", workspace=str(workspace), ref=ref)
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
        jobs = dict(
            connection.execute(
                sa.text(
                    "SELECT status, count(*) FROM procrastinate_jobs"
                    " WHERE task_name = 'effect' AND args->>'ref' LIKE 'c2-%' GROUP BY status"
                )
            ).all()
        )
        attempts = connection.execute(
            sa.text("SELECT count(*) FROM attempts WHERE task_ref LIKE 'c2-%'")
        ).scalar()
        # Attempts made after the effect already existed: the idempotency key did its job.
        neutralized = connection.execute(
            sa.text(
                "SELECT count(*) FROM attempts a JOIN effects e USING (task_ref)"
                " WHERE a.task_ref LIKE 'c2-%' AND a.started_at > e.done_at"
            )
        ).scalar()
        kills = connection.execute(sa.text("SELECT count(*) FROM kills")).scalar()
        # Resume delay: for each task with an attempt started before a kill of its worker
        # and finished after it, time from that kill to its effect.
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
    result = {
        "criterion": "C2 C3 C4",
        "engine": "procrastinate",
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
    write("c2-procrastinate", result)


def c5() -> None:
    import procrastinate_app

    rng = random.Random(SEED + 5)
    with procrastinate_app.app.open():
        ids = []
        for index in range(100):
            ref = f"c5-{index:03d}"
            ids.append(
                (
                    ref,
                    procrastinate_app.effect.configure(schedule_in={"seconds": 60}).defer(
                        key=f"key-{ref}", workspace=str(common.WORKSPACES[0]), ref=ref
                    ),
                )
            )
        cancelled = rng.sample(ids, 10)
        outcomes = {
            ref: procrastinate_app.app.job_manager.cancel_job_by_id(job_id)
            for ref, job_id in cancelled
        }
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        if scalar("SELECT count(*) FROM effects WHERE task_ref LIKE 'c5-%'") == 90:
            break
        time.sleep(5)
    time.sleep(10)
    cancelled_refs = [ref for ref, _ in cancelled]
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
    result = {
        "criterion": "C5",
        "engine": "procrastinate",
        "cancel_calls_succeeded": sum(1 for ok in outcomes.values() if ok),
        "cancelled_that_ran": ran_cancelled,
        "others_done": others_done,
        "details": {"cancelled": cancelled_refs},
    }
    result["passed"] = ran_cancelled == 0 and others_done == 90
    write("c5-procrastinate", result)


def c6_enqueue() -> None:
    import procrastinate_app

    # A few notes in each workspace, written under their own context.
    for workspace in common.WORKSPACES:
        with database.workspace_transaction(common.app_engine(), workspace) as connection:
            for index in range(5):
                connection.execute(
                    sa.text("INSERT INTO notes (workspace_id, body) VALUES (:w, :b)"),
                    {"w": workspace, "b": f"c6-note-{index}"},
                )
    with procrastinate_app.app.open():
        for index in range(200):
            workspace = common.WORKSPACES[index % 2]
            ref = f"c6-{index:03d}"
            procrastinate_app.read_notes.defer(key=f"key-{ref}", workspace=str(workspace), ref=ref)
            if index % 10 == 9:
                probe = f"c6-probe-{index:03d}"
                procrastinate_app.probe.defer(key=f"key-{probe}", workspace=str(workspace), ref=probe)
    print("220 tasks enqueued")


def c6_check() -> None:
    with common.admin_engine().connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT task_ref, workspace_id, seen_workspaces FROM effects"
                " WHERE task_ref LIKE 'c6-%'"
            )
        ).all()
        notify_listening = connection.execute(
            sa.text("SELECT count(*) FROM pg_stat_activity WHERE usename = 'otlet_app'"
                    " AND query ILIKE 'LISTEN%'")
        ).scalar()
    readers = [r for r in rows if not r.task_ref.startswith("c6-probe")]
    probes = [r for r in rows if r.task_ref.startswith("c6-probe")]
    leaks = [r.task_ref for r in readers if set(r.seen_workspaces) - {r.workspace_id}]
    blind = [r.task_ref for r in readers if not r.seen_workspaces]
    probe_leaks = [r.task_ref for r in probes if str(r.workspace_id).startswith("00000000")]
    result = {
        "criterion": "C6",
        "engine": "procrastinate",
        "readers_done": len(readers),
        "readers_with_foreign_rows": len(leaks),
        "readers_seeing_nothing": len(blind),
        "witnesses_done": len(probes),
        "witnesses_seeing_rows_without_context": len(probe_leaks),
        "listen_connections_of_app_role": notify_listening,
        "details": {"leaks": leaks, "probe_leaks": probe_leaks},
    }
    result["passed"] = (
        len(readers) == 200 and not leaks and not blind and len(probes) == 20 and not probe_leaks
    )
    write("c6-procrastinate", result)


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
