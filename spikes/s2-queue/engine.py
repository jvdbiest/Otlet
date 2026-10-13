# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2: the same few operations on either engine, chosen by S2_ENGINE (procrastinate, dbos)."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from typing import Any

import sqlalchemy as sa

NAME = os.environ.get("S2_ENGINE", "procrastinate")


@contextlib.contextmanager
def opened() -> Iterator[None]:
    if NAME == "procrastinate":
        import procrastinate_app

        with procrastinate_app.app.open():
            yield
    else:
        yield


def defer(
    task: str,
    ref: str,
    workspace: str,
    delay: float | None = None,
    connection: sa.Connection | None = None,
) -> Any:
    """Enqueue `task`; with `connection`, inside that SQLAlchemy transaction."""
    kwargs = {"key": f"key-{ref}", "workspace": workspace, "ref": ref}
    if NAME == "procrastinate":
        import procrastinate_app

        options: dict[str, Any] = {}
        if delay is not None:
            options["schedule_in"] = {"seconds": delay}
        if connection is not None:
            options["connection"] = connection.connection.driver_connection
        return getattr(procrastinate_app, task).configure(**options).defer(**kwargs)
    import dbos_app

    if connection is not None:
        handle = dbos_app.client().enqueue_in_transaction(
            connection, dbos_app.options(task, ref, delay), **kwargs
        )
        return handle.get_workflow_id()
    return dbos_app.enqueue(task, kwargs, ref, delay)


def cancel(job_id: Any) -> bool:
    if NAME == "procrastinate":
        import procrastinate_app

        return bool(procrastinate_app.app.job_manager.cancel_job_by_id(job_id))
    import dbos_app

    dbos_app.client().cancel_workflow(job_id)
    return True


def apply_schema() -> None:
    if NAME == "procrastinate":
        import procrastinate_app

        procrastinate_app.apply_schema()
    else:
        import dbos_app

        dbos_app.apply_schema()


def count_jobs_query() -> str:
    """Jobs whose reference matches :p (C1)."""
    if NAME == "procrastinate":
        return "SELECT count(*) FROM procrastinate_jobs WHERE args->>'ref' LIKE :p"
    return "SELECT count(*) FROM dbos.workflow_status WHERE workflow_uuid LIKE :p"


def jobs_by_status_query() -> str:
    if NAME == "procrastinate":
        return (
            "SELECT status::text, count(*) FROM procrastinate_jobs"
            " WHERE args->>'ref' LIKE 'c2-%' GROUP BY status"
        )
    return (
        "SELECT status, count(*) FROM dbos.workflow_status"
        " WHERE workflow_uuid LIKE 'c2-%' GROUP BY status"
    )
