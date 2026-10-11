# SPDX-License-Identifier: AGPL-3.0-or-later
"""Scheduler role. Until the job queue exists (S2), it only proves the role starts and stays
alive; the leader lock on PostgreSQL comes with the queue (TECH_CHOICES §9.4)."""

import threading

from otlet.platform import process
from otlet.platform.config import Settings

ROLE = "scheduler"
INTERVAL_SECONDS = 5.0


def run(settings: Settings, stop: threading.Event) -> None:
    process.run_loop(ROLE, settings.run_dir, lambda: None, stop, INTERVAL_SECONDS)
