# SPDX-License-Identifier: AGPL-3.0-or-later
"""The job queue on a real PostgreSQL (F04, ADR-0022): transactional enqueueing, the worker,
the periodic jobs, and the resumption of a job after a brutal stop of its worker."""

import asyncio
import importlib
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import procrastinate
import pytest
import sqlalchemy as sa

from integration_support import TestDatabase, requires_database
from otlet.entrypoints.worker import main as worker
from otlet.jobs.adapters import procrastinate_queue
from otlet.jobs.application.registry import JobEnvironment, Registry, registry
from otlet.platform import database as db

pytestmark = requires_database

SLOW_JOBS = Path(__file__).with_name("slow_jobs.py")

test_jobs = Registry()


@test_jobs.job("test.record")
def record(environment: JobEnvironment, ref: str) -> None:
    with environment.engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO instance_settings (key, value) VALUES (:key, 'true')"),
            {"key": f"recorded:{ref}"},
        )


def setting_exists(database: TestDatabase, key: str) -> bool:
    with db.create_engine(database.admin_url).connect() as connection:
        query = sa.text("SELECT count(*) FROM instance_settings WHERE key = :key")
        return bool(connection.execute(query, {"key": key}).scalar_one() == 1)


def job_rows(database: TestDatabase, task: str) -> list[tuple[str, int]]:
    """(status, attempts) of each job of `task`, oldest first."""
    with db.create_engine(database.admin_url).connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT status::text, attempts FROM procrastinate_jobs"
                " WHERE task_name = :task ORDER BY id"
            ),
            {"task": task},
        ).all()
    return [(str(status), int(attempts)) for status, attempts in rows]


def run_until_empty(app: procrastinate.App) -> None:
    async def work() -> None:
        async with app.open_async():
            await procrastinate_queue.run_worker(app, wait=False)

    asyncio.run(work())


@pytest.fixture
def engine(migrated: TestDatabase) -> sa.Engine:
    return db.create_engine(migrated.app_url)


def test_a_job_exists_only_if_its_transaction_commits(
    migrated: TestDatabase, engine: sa.Engine
) -> None:
    app = procrastinate_queue.build_app(migrated.app_url)
    with pytest.raises(RuntimeError):
        with engine.begin() as connection:
            procrastinate_queue.enqueue(app, connection, "test.record", ref="rolled-back")
            raise RuntimeError("the business transaction fails")
    with engine.begin() as connection:
        job_id = procrastinate_queue.enqueue(app, connection, "test.record", ref="committed")
    assert job_id > 0
    assert job_rows(migrated, "test.record") == [("todo", 0)]


def test_the_worker_runs_an_enqueued_job(migrated: TestDatabase, engine: sa.Engine) -> None:
    app = procrastinate_queue.build_app(migrated.app_url, JobEnvironment(engine), test_jobs)
    with engine.begin() as connection:
        procrastinate_queue.enqueue(app, connection, "test.record", ref="run")
    run_until_empty(app)
    assert setting_exists(migrated, "recorded:run")
    assert job_rows(migrated, "test.record") == [("succeeded", 1)]


def test_the_worker_schedules_its_periodic_jobs(migrated: TestDatabase) -> None:
    worker.load_jobs()
    app = procrastinate_queue.build_app(
        migrated.app_url, JobEnvironment(db.create_engine(migrated.app_url)), registry
    )
    periodic = {name for name, _ in app.periodic_registry.periodic_tasks}
    assert {procrastinate_queue.RETRY_STALLED, "identity.purge_sessions"} <= periodic


def test_expired_sessions_are_purged(migrated: TestDatabase, engine: sa.Engine) -> None:
    worker.load_jobs()
    user = uuid.uuid4()
    with db.create_engine(migrated.admin_url).begin() as connection:
        connection.execute(
            sa.text("INSERT INTO users (id, display_name) VALUES (:id, 'Joël')"), {"id": user}
        )
        for age in ("1 minute", "13 hours"):
            connection.execute(
                sa.text(
                    "INSERT INTO user_sessions (user_id, token_hash, created_at, last_seen_at,"
                    " reauthenticated_at) VALUES (:user, :hash, now(),"
                    " now() - CAST(:age AS interval), now())"
                ),
                {"user": user, "hash": os.urandom(32), "age": age},
            )
    app = procrastinate_queue.build_app(migrated.app_url, JobEnvironment(engine), registry)
    with engine.begin() as connection:
        # As the worker defers it every hour: with the due time.
        procrastinate_queue.enqueue(app, connection, "identity.purge_sessions", timestamp=0)
    run_until_empty(app)
    with db.create_engine(migrated.admin_url).connect() as connection:
        left = connection.execute(sa.text("SELECT count(*) FROM user_sessions")).scalar_one()
    assert left == 1


@pytest.fixture
def slow_worker(migrated: TestDatabase) -> Iterator[subprocess.Popen[bytes]]:
    environment = {**os.environ, "PYTHONPATH": str(SLOW_JOBS.parent)}
    process = subprocess.Popen(  # noqa: S603 (fixed command, test only)
        [sys.executable, str(SLOW_JOBS), migrated.app_url], env=environment
    )
    yield process
    if process.poll() is None:
        process.kill()
        process.wait()


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL is POSIX")
def test_a_job_interrupted_by_a_brutal_stop_is_resumed(
    migrated: TestDatabase,
    engine: sa.Engine,
    slow_worker: subprocess.Popen[bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(SLOW_JOBS.parent))
    slow_jobs = importlib.import_module("slow_jobs")

    app = procrastinate_queue.build_app(migrated.app_url)
    with engine.begin() as connection:
        procrastinate_queue.enqueue(app, connection, "test.slow", ref="killed")

    deadline = time.monotonic() + 30
    while not setting_exists(migrated, "started:killed"):
        assert time.monotonic() < deadline, "the worker never started the job"
        time.sleep(0.2)
    slow_worker.kill()  # SIGKILL: no chance to release the job
    slow_worker.wait()
    assert [status for status, _ in job_rows(migrated, "test.slow")] == ["doing"]

    # The worker would be declared stalled after 30 s of silence: age its heartbeat instead of
    # waiting, then run what the periodic job jobs.retry_stalled runs.
    with db.create_engine(migrated.admin_url).begin() as connection:
        connection.execute(
            sa.text("UPDATE procrastinate_workers SET last_heartbeat = now() - interval '1 minute'")
        )
    resuming = procrastinate_queue.build_app(
        migrated.app_url, JobEnvironment(engine), slow_jobs.registry
    )

    async def retry() -> int:
        async with resuming.open_async():
            return await procrastinate_queue.retry_stalled_jobs(resuming)

    assert asyncio.run(retry()) == 1
    monkeypatch.setenv("OTLET_TEST_FAST", "1")
    run_until_empty(resuming)
    assert setting_exists(migrated, "finished:killed")
    assert [status for status, _ in job_rows(migrated, "test.slow")] == ["succeeded"]
