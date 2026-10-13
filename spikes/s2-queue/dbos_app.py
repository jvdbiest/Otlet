# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2: DBOS Transact application of the bench (S2.5).

Worker:  python dbos_app.py worker      (executor id = S2_WORKER, so a restarted container
                                          recovers its own interrupted workflows)
Schema:  python dbos_app.py schema      (system tables in schema "dbos" of otlet_s2,
                                          created by the superuser, then granted to otlet_app)

The system database is the application database, so that a workflow can be enqueued in the
application's own transaction (DBOSClient.enqueue_in_transaction). Each task is a workflow
with one step; a step interrupted by a kill is run again on recovery (at least once), which
the idempotency key neutralizes. Queue "bench": 4 workflows at a time per worker.
"""

from __future__ import annotations

import sys
import threading
from functools import cache
from typing import Any

from dbos import DBOS, DBOSClient, DBOSConfig, EnqueueOptions

import common

QUEUE = "bench"
CONCURRENCY = 4


def config(run_migrations: bool, url_variable: str = "S2_APP_URL") -> DBOSConfig:
    return {
        "name": "otlet-s2",
        "system_database_url": common.sqlalchemy_url(common.env(url_variable)),
        "executor_id": common.worker_name(),
        "run_migrations": run_migrations,
        "log_level": "WARNING",
    }


@cache
def client() -> DBOSClient:
    return DBOSClient(system_database_url=common.sqlalchemy_url(common.env("S2_APP_URL")))


def options(name: str, workflow_id: str, delay: float | None = None) -> EnqueueOptions:
    result: EnqueueOptions = {"workflow_name": name, "queue_name": QUEUE, "workflow_id": workflow_id}
    if delay is not None:
        result["delay_seconds"] = delay
    return result


def register() -> None:
    """Workflows and steps; the queue is registered after launch (persisted in the database)."""

    @DBOS.step()
    def effect_step(key: str, workspace: str, ref: str, read: bool) -> None:
        common.perform(ref, key, workspace, read_notes=read)

    @DBOS.workflow(name="effect")
    def effect(key: str, workspace: str, ref: str) -> None:
        effect_step(key, workspace, ref, False)

    @DBOS.workflow(name="read_notes")
    def read_notes(key: str, workspace: str, ref: str) -> None:
        effect_step(key, workspace, ref, True)

    @DBOS.step()
    def probe_step(key: str, workspace: str, ref: str) -> None:
        visible = common.probe_without_context()
        common.perform(ref, key, workspace if visible == 0 else "00000000-0000-0000-0000-000000000000")

    @DBOS.workflow(name="probe")
    def probe(key: str, workspace: str, ref: str) -> None:
        probe_step(key, workspace, ref)


def apply_schema() -> None:
    import sqlalchemy as sa

    register()
    DBOS(config=config(run_migrations=True, url_variable="S2_ADMIN_URL"))
    DBOS.launch()
    DBOS.register_queue(QUEUE, worker_concurrency=CONCURRENCY)
    DBOS.destroy()
    with common.admin_engine().begin() as connection:
        for statement in (
            "GRANT USAGE ON SCHEMA dbos TO otlet_app",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dbos TO otlet_app",
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA dbos TO otlet_app",
            "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA dbos TO otlet_app",
        ):
            connection.execute(sa.text(statement))


def worker() -> None:
    register()
    DBOS(config=config(run_migrations=False))
    DBOS.launch()
    DBOS.register_queue(QUEUE, worker_concurrency=CONCURRENCY)
    threading.Event().wait()


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "schema":
        apply_schema()
    elif command == "worker":
        worker()
    else:
        print(__doc__)
        return 2
    return 0


def enqueue(name: str, kwargs: dict[str, Any], workflow_id: str, delay: float | None = None) -> str:
    handle = client().enqueue(options(name, workflow_id, delay), **kwargs)
    return handle.get_workflow_id()


if __name__ == "__main__":
    sys.exit(main())
