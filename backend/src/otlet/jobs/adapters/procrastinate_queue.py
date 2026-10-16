# SPDX-License-Identifier: AGPL-3.0-or-later
"""The job queue on Procrastinate (ADR-0022), with the settings that S2 validated.

- Workers send a heartbeat every 10 s and are declared stalled after 30 s without one.
- `jobs.retry_stalled`, deferred by the workers themselves every minute, puts back in the queue
  the jobs of stalled workers, which Procrastinate does not do by itself. A job interrupted by a
  brutal stop is thus resumed within about two minutes.
- Enqueueing uses the connection of the caller's transaction (`enqueue`).
"""

import functools
from collections.abc import Iterable
from typing import Any

import procrastinate
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from otlet.jobs.application.registry import (
    MAINTENANCE_QUEUE,
    QUEUES,
    JobDefinition,
    JobEnvironment,
)

HEARTBEAT_SECONDS = 10.0
STALLED_AFTER_SECONDS = 30.0
CONCURRENCY = 4
RETRY_WAIT_SECONDS = 2
RETRY_STALLED = "jobs.retry_stalled"


def conninfo(database_url: str) -> str:
    """The libpq form of a SQLAlchemy URL (postgresql+psycopg://… → postgresql://…)."""
    url = make_url(database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def _runner(definition: JobDefinition, environment: JobEnvironment) -> Any:
    @functools.wraps(definition.function)
    def run(**kwargs: Any) -> None:
        if definition.cron is not None:
            # Procrastinate passes the due time to periodic jobs; ours do not need it.
            kwargs.pop("timestamp", None)
        definition.function(environment, **kwargs)

    return run


def build_app(
    database_url: str,
    environment: JobEnvironment | None = None,
    definitions: Iterable[JobDefinition] = (),
) -> procrastinate.App:
    """The Procrastinate application. Without an environment it only enqueues (the API);
    with one it can run the given jobs (the worker)."""
    app = procrastinate.App(
        connector=procrastinate.PsycopgConnector(conninfo=conninfo(database_url))
    )
    if environment is None:
        return app
    for definition in definitions:
        task = app.task(
            name=definition.name,
            queue=definition.queue,
            retry=procrastinate.RetryStrategy(
                max_attempts=definition.attempts - 1, wait=RETRY_WAIT_SECONDS
            ),
        )(_runner(definition, environment))
        if definition.cron is not None:
            app.periodic(cron=definition.cron, periodic_id=definition.name)(task)

    @app.periodic(cron="* * * * *", periodic_id=RETRY_STALLED)
    @app.task(
        name=RETRY_STALLED,
        queue=MAINTENANCE_QUEUE,
        queueing_lock=RETRY_STALLED,
        pass_context=True,
    )
    async def retry_stalled(context: procrastinate.JobContext, timestamp: int) -> None:
        await retry_stalled_jobs(context.app)

    return app


async def retry_stalled_jobs(
    app: procrastinate.App, stalled_after: float = STALLED_AFTER_SECONDS
) -> int:
    """Puts back in the queue the jobs held by workers silent for `stalled_after` seconds."""
    stalled = list(await app.job_manager.get_stalled_jobs(seconds_since_heartbeat=stalled_after))
    for job in stalled:
        await app.job_manager.retry_job(job)
    return len(stalled)


async def run_worker(app: procrastinate.App, *, wait: bool = True) -> None:
    """Runs a worker on every queue. With wait=False it stops once the queues are empty."""
    await app.run_worker_async(
        queues=list(QUEUES),
        concurrency=CONCURRENCY,
        wait=wait,
        update_heartbeat_interval=HEARTBEAT_SECONDS,
        stalled_worker_timeout=STALLED_AFTER_SECONDS,
        install_signal_handlers=wait,
    )


def enqueue(app: procrastinate.App, connection: sa.Connection, name: str, **kwargs: Any) -> int:
    """Enqueues the job `name` inside the transaction of `connection`: if the transaction rolls
    back, the job never existed. Returns the job identifier."""
    driver_connection = connection.connection.driver_connection
    deferrer = app.configure_task(name, allow_unknown=True, connection=driver_connection)
    return int(deferrer.defer(**kwargs))
