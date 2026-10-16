# SPDX-License-Identifier: AGPL-3.0-or-later
"""Worker role: runs the background jobs of every module (ADR-0022).

It also defers the periodic jobs, Procrastinate's way: each worker tries, and a unique row per
due run lets only one of them succeed. The heartbeat file read by the container health check
is written from the worker's own event loop, so it stops when the loop is stuck.
"""

import asyncio
import importlib
import logging

from otlet.jobs.adapters import procrastinate_queue
from otlet.jobs.application.registry import JobEnvironment, registry
from otlet.platform import database, process
from otlet.platform.config import Settings

logger = logging.getLogger(__name__)

ROLE = "worker"
INTERVAL_SECONDS = 5.0
# Modules whose jobs this worker runs; importing one registers its jobs.
JOB_MODULES = ("otlet.identity.adapters.jobs",)


def load_jobs() -> None:
    for module in JOB_MODULES:
        importlib.import_module(module)


async def _beat(settings: Settings) -> None:
    while True:
        process.beat(settings.run_dir, ROLE)
        await asyncio.sleep(INTERVAL_SECONDS)


async def _run(settings: Settings) -> None:
    load_jobs()
    url = settings.require_database_url()
    environment = JobEnvironment(engine=database.create_engine(url))
    app = procrastinate_queue.build_app(url, environment, registry)
    async with app.open_async():
        beating = asyncio.create_task(_beat(settings))
        try:
            logger.info("%s started", ROLE)
            await procrastinate_queue.run_worker(app)
        finally:
            beating.cancel()
            logger.info("%s stopped", ROLE)


def run(settings: Settings) -> None:
    """Runs until SIGTERM or SIGINT, which Procrastinate handles: running jobs finish first."""
    asyncio.run(_run(settings))
