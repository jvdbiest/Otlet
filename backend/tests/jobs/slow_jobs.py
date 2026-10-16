# SPDX-License-Identifier: AGPL-3.0-or-later
"""Jobs of the brutal-stop test (test_queue.py), run by a worker in a separate process.

`test.slow` records that it started, then blocks until its process is killed; with
OTLET_TEST_FAST=1 it records that it finished instead.
"""

import asyncio
import os
import sys
import time

import sqlalchemy as sa

from otlet.jobs.adapters import procrastinate_queue
from otlet.jobs.application.registry import JobEnvironment, Registry
from otlet.platform import database

registry = Registry()


def mark(environment: JobEnvironment, key: str) -> None:
    with environment.engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO instance_settings (key, value) VALUES (:key, 'true')"
                " ON CONFLICT (key) DO NOTHING"
            ),
            {"key": key},
        )


@registry.job("test.slow")
def slow(environment: JobEnvironment, ref: str) -> None:
    if os.environ.get("OTLET_TEST_FAST") == "1":
        mark(environment, f"finished:{ref}")
        return
    mark(environment, f"started:{ref}")
    time.sleep(3600)


def main(database_url: str) -> None:
    environment = JobEnvironment(engine=database.create_engine(database_url))
    app = procrastinate_queue.build_app(database_url, environment, registry)

    async def work() -> None:
        async with app.open_async():
            await procrastinate_queue.run_worker(app)

    asyncio.run(work())


if __name__ == "__main__":
    main(sys.argv[1])
