# SPDX-License-Identifier: AGPL-3.0-or-later
"""Declaring jobs without depending on the queue engine.

A job is a plain function that receives the JobEnvironment first, then its keyword arguments.
Arguments are JSON values: identifiers, never objects. A job that touches workspace data takes
the workspace identifier and opens its own scoped transaction: a job never runs in a context it
did not set itself (ADR-0028).
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import sqlalchemy as sa

DEFAULT_QUEUE = "default"
MAINTENANCE_QUEUE = "maintenance"
QUEUES = (DEFAULT_QUEUE, MAINTENANCE_QUEUE)


@dataclass(frozen=True, slots=True)
class JobEnvironment:
    """What the worker hands to every job."""

    engine: sa.Engine


JobFunction = Callable[..., None]


@dataclass(frozen=True, slots=True)
class JobDefinition:
    name: str
    function: JobFunction
    queue: str = DEFAULT_QUEUE
    # A cron expression (UTC) for jobs the worker defers by itself.
    cron: str | None = None
    # Attempts in all, the first included; a job failing that often stays failed.
    attempts: int = 5


@dataclass
class Registry:
    definitions: dict[str, JobDefinition] = field(default_factory=dict)

    def job(
        self, name: str, *, queue: str = DEFAULT_QUEUE, cron: str | None = None, attempts: int = 5
    ) -> Callable[[JobFunction], JobFunction]:
        if queue not in QUEUES:
            raise ValueError(f"unknown queue {queue!r}")

        def register(function: JobFunction) -> JobFunction:
            if name in self.definitions:
                raise ValueError(f"job {name!r} is already declared")
            self.definitions[name] = JobDefinition(name, function, queue, cron, attempts)
            return function

        return register

    def __iter__(self) -> Iterator[JobDefinition]:
        return iter(self.definitions.values())


# The registry of the application; the worker imports the modules that fill it.
registry = Registry()
job = registry.job
