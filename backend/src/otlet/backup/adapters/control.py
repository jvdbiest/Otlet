# SPDX-License-Identifier: AGPL-3.0-or-later
"""The settings, request and state of the backups, in `instance_settings` (ARCHITECTURE §20.3):
the API writes the schedule and the requests, the backup service its state."""

import json
from dataclasses import asdict
from typing import Any

import sqlalchemy as sa

from otlet.backup.application.service import Request, State
from otlet.backup.domain.backup import Schedule

SCHEDULE_KEY = "backup.schedule"
REQUEST_KEY = "backup.request"
STATE_KEY = "backup.state"


class PostgresControl:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def _read(self, key: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            value = connection.execute(
                sa.text("SELECT value FROM instance_settings WHERE key = :key"), {"key": key}
            ).scalar()
        return value if isinstance(value, dict) else None

    def _write(self, key: str, value: dict[str, Any]) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO instance_settings (key, value)"
                    " VALUES (:key, CAST(:value AS jsonb))"
                    " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()"
                ),
                {"key": key, "value": json.dumps(value)},
            )

    def schedule(self) -> Schedule:
        value = self._read(SCHEDULE_KEY)
        if value is None:
            return Schedule()
        known = set(Schedule.__dataclass_fields__)
        return Schedule(**{k: v for k, v in value.items() if k in known})

    def save_schedule(self, schedule: Schedule) -> None:
        self._write(SCHEDULE_KEY, asdict(schedule))

    def request(self) -> Request | None:
        value = self._read(REQUEST_KEY)
        if value is None:
            return None
        known = set(Request.__dataclass_fields__)
        return Request(**{k: v for k, v in value.items() if k in known})

    def save_request(self, request: Request) -> None:
        self._write(REQUEST_KEY, asdict(request))

    def state(self) -> State:
        value = self._read(STATE_KEY)
        if value is None:
            return State()
        known = set(State.__dataclass_fields__)
        return State(**{k: v for k, v in value.items() if k in known})

    def save_state(self, state: State) -> None:
        self._write(STATE_KEY, asdict(state))
