# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2: Procrastinate application of the bench (S2.2 to S2.4).

Worker:  python procrastinate_app.py worker
Schema:  python procrastinate_app.py schema   (migration role, objects owned by otlet_owner)

Settings fixed before measurement (docs/spikes/S2.md §3.3): a worker sends a heartbeat every
10 s and is declared stalled after 30 s without one; a periodic task, every minute, retries
the jobs of stalled workers (Procrastinate does not do it by itself); a failing job is retried
up to 10 times, 2 s apart.
"""

from __future__ import annotations

import sys

import procrastinate
import procrastinate.schema
import psycopg

import common

HEARTBEAT_SECONDS = 10
STALLED_AFTER_SECONDS = 30
CONCURRENCY = 4

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=common.env("S2_APP_URL")),
)

RETRY = procrastinate.RetryStrategy(max_attempts=10, wait=2)


@app.task(name="effect", queue="bench", retry=RETRY)
def effect(key: str, workspace: str, ref: str) -> None:
    common.perform(ref, key, workspace)


@app.task(name="read_notes", queue="bench", retry=RETRY)
def read_notes(key: str, workspace: str, ref: str) -> None:
    common.perform(ref, key, workspace, read_notes=True)


@app.task(name="probe", queue="bench", retry=RETRY)
def probe(key: str, workspace: str, ref: str) -> None:
    """C6 witness: no context posed; records how many notes it could see in seen_workspaces."""
    visible = common.probe_without_context()
    common.perform(ref, key, workspace if visible == 0 else "00000000-0000-0000-0000-000000000000")


@app.periodic(cron="* * * * *", periodic_id="retry_stalled")
@app.task(name="retry_stalled", queue="maintenance", queueing_lock="retry_stalled", pass_context=True)
async def retry_stalled(context: procrastinate.JobContext, timestamp: int) -> None:
    stalled = await context.app.job_manager.get_stalled_jobs(
        seconds_since_heartbeat=STALLED_AFTER_SECONDS
    )
    for job in stalled:
        await context.app.job_manager.retry_job(job)


def apply_schema() -> None:
    sql = procrastinate.schema.SchemaManager.get_schema()
    with psycopg.connect(common.env("S2_MIGRATOR_URL"), autocommit=True) as connection:
        connection.execute("SET ROLE otlet_owner")
        connection.execute(sql)  # type: ignore[arg-type]


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "schema":
        apply_schema()
        common.apply_bench_schema()
    elif command == "worker":
        app.run_worker(
            queues=["bench", "maintenance"],
            concurrency=CONCURRENCY,
            update_heartbeat_interval=HEARTBEAT_SECONDS,
            stalled_worker_timeout=STALLED_AFTER_SECONDS,
            install_signal_handlers=True,
        )
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
