# SPDX-License-Identifier: AGPL-3.0-or-later
"""The backup service (ADR-0042): it checks its destination, takes the daily backup when due or
when the administrator asks for one, keeps what must be kept, and says how it went. It runs in
its own process, with the owner role; the API only reads its state and leaves requests."""

import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from otlet.backup.application.backups import Backups
from otlet.backup.domain.backup import Schedule, due, moment_of

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Request:
    """« Sauvegarder maintenant »: one at a time."""

    requested_at: str
    requested_by: str | None
    status: str  # "pending", "running", "done", "failed"
    name: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class State:
    """What the service last saw of its destination, and how its last backup went."""

    checked_at: str | None = None
    writable: bool = False
    free_bytes: int | None = None
    total_bytes: int | None = None
    error: str | None = None
    running: bool = False
    last_name: str | None = None
    last_error: str | None = None
    encrypted: bool = False


class Control(Protocol):
    def schedule(self) -> Schedule: ...

    def save_schedule(self, schedule: Schedule) -> None: ...

    def request(self) -> Request | None: ...

    def save_request(self, request: Request) -> None: ...

    def state(self) -> State: ...

    def save_state(self, state: State) -> None: ...


def probe(destination: Path) -> tuple[bool, int | None, int | None, str | None]:
    """Whether the destination takes a file, and its free and total space."""
    try:
        destination.mkdir(parents=True, exist_ok=True)
        test = destination / ".probe"
        test.write_bytes(b"otlet")
        test.unlink()
        usage = shutil.disk_usage(destination)
    except OSError as error:
        return False, None, None, f"{type(error).__name__}: {error.strerror or error}"
    return True, usage.free, usage.total, None


class BackupService:
    def __init__(
        self,
        backups: Backups,
        destination: Path,
        control: Control,
        encrypted: bool,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._backups = backups
        self._destination = destination
        self._control = control
        self._encrypted = encrypted
        self._clock = clock

    def _last_daily(self) -> datetime | None:
        """The latest backup that counts for the day: any but a restore's own."""
        for name in self._backups.names():
            if self._backups.manifest(name).reason != "before-restore":
                return moment_of(name)
        return None

    def step(self) -> str | None:
        """One round: check the destination, then back up if asked or due. The name taken."""
        now = self._clock()
        writable, free, total, error = probe(self._destination)
        state = replace(
            self._control.state(),
            checked_at=now.isoformat(),
            writable=writable,
            free_bytes=free,
            total_bytes=total,
            error=error,
            encrypted=self._encrypted,
            running=False,
        )
        self._control.save_state(state)
        request = self._control.request()
        schedule = self._control.schedule()
        if request is not None and request.status == "pending":
            reason = "manual"
        elif due(now, self._last_daily(), schedule):
            reason = "scheduled"
        else:
            return None
        if not writable:
            if request is not None and request.status == "pending":
                self._control.save_request(replace(request, status="failed", error=error))
            return None
        if reason == "manual" and request is not None:
            self._control.save_request(replace(request, status="running"))
        self._control.save_state(replace(state, running=True))
        try:
            name = self._backups.run(reason)
            self._backups.prune(schedule.daily, schedule.weekly)
        except Exception as failure:  # any failure is shown, then the service carries on
            logger.exception("backup failed")
            message = f"{type(failure).__name__}: {failure}"[:500]
            self._control.save_state(replace(state, running=False, last_error=message))
            if reason == "manual" and request is not None:
                self._control.save_request(replace(request, status="failed", error=message))
            return None
        manifest = self._backups.manifest(name)
        last_error = None if manifest.verified else "; ".join(manifest.problems[:3])
        self._control.save_state(
            replace(state, running=False, last_name=name, last_error=last_error)
        )
        if reason == "manual" and request is not None:
            self._control.save_request(replace(request, status="done", name=name))
        return name


def passphrase_from(path: str) -> str:
    """The passphrase of the backups, from its file; empty when there is none."""
    if not path or not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as file:
        return file.read().strip()
