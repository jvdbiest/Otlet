# SPDX-License-Identifier: AGPL-3.0-or-later
"""Scheduler role: the deadlines of the domain (ARCHITECTURE §12.5, ADR-0030).

A single scheduler leads at a time (otlet.platform.leader). The leader enqueues the work that
is due; the workers do it. Deadlines live in the database, so a deadline missed while no
scheduler ran is caught up once at restart, per type:

- source collection (U01): a source whose next collection is past is collected once, then
  rescheduled one interval later, however many runs were missed.

Without a database (tests of the role itself), it only beats.
"""

import logging
import threading
import time

import sqlalchemy as sa

from otlet.collection.adapters.postgres import PostgresCollectionStore
from otlet.collection.application.collection import CLAIM_BATCH
from otlet.jobs.adapters import procrastinate_queue
from otlet.platform import database, process
from otlet.platform.config import Settings
from otlet.platform.leader import LeaderLock

logger = logging.getLogger(__name__)

ROLE = "scheduler"
INTERVAL_SECONDS = 5.0
COLLECTION_EVERY_SECONDS = 30.0


class Scheduler:
    def __init__(self, settings: Settings) -> None:
        url = settings.require_database_url()
        engine = database.create_engine(url)
        self._lock = LeaderLock(engine)
        self._collection = PostgresCollectionStore(engine, procrastinate_queue.enqueuer(url))
        self._next_collection = 0.0

    def step(self) -> None:
        if not self._lock.hold():
            return
        now = time.monotonic()
        if now >= self._next_collection:
            self._next_collection = now + COLLECTION_EVERY_SECONDS
            try:
                claimed = self._collection.claim_due_sources(CLAIM_BATCH)
            except sa.exc.SQLAlchemyError:
                logger.exception("dispatching the due collections failed")
                return
            if claimed:
                logger.info("%s source collections enqueued", claimed)

    def close(self) -> None:
        self._lock.release()


def run(settings: Settings, stop: threading.Event) -> None:
    if settings.database_url is None:
        process.run_loop(ROLE, settings.run_dir, lambda: None, stop, INTERVAL_SECONDS)
        return
    scheduler = Scheduler(settings)
    try:
        process.run_loop(ROLE, settings.run_dir, scheduler.step, stop, INTERVAL_SECONDS)
    finally:
        scheduler.close()
