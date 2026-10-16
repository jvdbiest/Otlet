# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the identity module."""

import logging

import sqlalchemy as sa

from otlet.identity.domain import model
from otlet.jobs.application.registry import MAINTENANCE_QUEUE, JobEnvironment, job

logger = logging.getLogger(__name__)

PURGE_SESSIONS = "identity.purge_sessions"


@job(PURGE_SESSIONS, queue=MAINTENANCE_QUEUE, cron="17 * * * *")
def purge_sessions(environment: JobEnvironment) -> None:
    """Every hour: deletes the sessions that nobody presented again after they expired
    (ADR-0029), and the stale sign-in throttle counters."""
    with environment.engine.begin() as connection:
        purged = connection.execute(
            sa.text("SELECT purge_expired_sessions(:idle, :lifetime, :window)"),
            {
                "idle": model.SESSION_IDLE_TIMEOUT,
                "lifetime": model.SESSION_LIFETIME,
                "window": model.THROTTLE_WINDOW,
            },
        ).scalar_one()
    logger.info("purged %s expired sessions", purged)
