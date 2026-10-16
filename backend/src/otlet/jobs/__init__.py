# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs (ADR-0022): the only module that knows Procrastinate.

Other modules declare their jobs with `otlet.jobs.application.registry.job` and enqueue them
with `otlet.jobs.adapters.procrastinate_queue.enqueue`, on the connection of their own
transaction, so a job exists if and only if that transaction commits.
"""
