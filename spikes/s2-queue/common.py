# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2: what both engines share — connections, bench tables, the task body (docs/spikes/S2.md §3.1).

Environment: S2_ADMIN_URL (superuser, libpq form), S2_MIGRATOR_URL, S2_APP_URL (libpq form).
"""

from __future__ import annotations

import os
import random
import time
import uuid
from functools import cache

import psycopg
import sqlalchemy as sa

from otlet.platform import database

WORKSPACES = (
    uuid.UUID("018f0000-0000-7000-8000-0000000000a1"),
    uuid.UUID("018f0000-0000-7000-8000-0000000000b2"),
)

BENCH_SCHEMA = """
SET ROLE otlet_owner;
DROP TABLE IF EXISTS effects, attempts, notes, kills CASCADE;
-- Instrumentation of the bench, outside row-level security.
CREATE TABLE effects (
    idempotency_key text PRIMARY KEY,
    task_ref        text NOT NULL,
    workspace_id    uuid NOT NULL,
    seen_workspaces uuid[] NOT NULL DEFAULT '{}',
    done_at         timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE attempts (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_ref    text NOT NULL,
    worker      text NOT NULL,
    started_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE kills (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    worker    text NOT NULL,
    killed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
-- Business rows, under forced row-level security (C1, C6).
CREATE TABLE notes (
    workspace_id uuid NOT NULL,
    id           uuid NOT NULL DEFAULT uuidv7(),
    body         text NOT NULL,
    PRIMARY KEY (workspace_id, id)
);
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_isolation ON notes
    USING (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid);
RESET ROLE;
"""


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is not set")
    return value


def sqlalchemy_url(libpq_url: str) -> str:
    return libpq_url.replace("postgresql://", "postgresql+psycopg://", 1)


@cache
def app_engine() -> sa.Engine:
    return database.create_engine(sqlalchemy_url(env("S2_APP_URL")), pool_size=10, max_overflow=0)


@cache
def admin_engine() -> sa.Engine:
    return database.create_engine(sqlalchemy_url(env("S2_ADMIN_URL")))


def worker_name() -> str:
    return os.environ.get("S2_WORKER", f"pid-{os.getpid()}")


def apply_bench_schema() -> None:
    with psycopg.connect(env("S2_MIGRATOR_URL"), autocommit=True) as connection:
        connection.execute(BENCH_SCHEMA)


def perform(task_ref: str, key: str, workspace: str, read_notes: bool = False) -> None:
    """The body of every bench task: attempt, simulated external call, idempotent effect.

    The effect is written in another transaction than the one that closes the job, so a kill
    between the two leads to a new attempt, which the idempotency key must neutralize.
    """
    engine = app_engine()
    with engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO attempts (task_ref, worker) VALUES (:t, :w)"),
            {"t": task_ref, "w": worker_name()},
        )
    time.sleep(random.uniform(0.05, 0.5))  # noqa: S311 (simulated external call)
    seen: list[uuid.UUID] = []
    if read_notes:
        with database.workspace_transaction(engine, uuid.UUID(workspace)) as connection:
            seen = list(connection.execute(sa.text("SELECT DISTINCT workspace_id FROM notes")).scalars())
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO effects (idempotency_key, task_ref, workspace_id, seen_workspaces)"
                " VALUES (:k, :t, :w, :s) ON CONFLICT (idempotency_key) DO NOTHING"
            ),
            {"k": key, "t": task_ref, "w": workspace, "s": seen},
        )


def probe_without_context() -> int:
    """C6 witness: rows visible on an application connection without workspace context."""
    with app_engine().connect() as connection:
        return int(connection.execute(sa.text("SELECT count(*) FROM notes")).scalar() or 0)
