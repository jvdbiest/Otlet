# SPDX-License-Identifier: AGPL-3.0-or-later
"""What a backup is (ADR-0042): its name, its manifest, and which ones are kept."""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

# A backup is a folder named after its moment, in UTC: they sort by name.
NAME_FORMAT = "%Y-%m-%dT%H%M%SZ"
MANIFEST = "manifest.json"
DATABASE = "database.dump"
FILES = "files"
SECRETS = "secrets"
ENCRYPTED = ".enc"  # suffix of every file of an encrypted backup
FORMAT_VERSION = 1

# Kept by default (ADR-0042): one a day for a week, one a week for a month.
DAILY = 7
WEEKLY = 4


def name_of(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(NAME_FORMAT)


def moment_of(name: str) -> datetime | None:
    """The moment of a backup from its folder's name; None for any other folder."""
    try:
        return datetime.strptime(name, NAME_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def kept(moments: list[datetime], daily: int = DAILY, weekly: int = WEEKLY) -> set[datetime]:
    """The backups to keep: the latest of each of the `daily` most recent days that have one,
    and the latest of each of the `weekly` most recent ISO weeks that have one. The latest
    backup is always kept."""
    keep: set[datetime] = set()
    days: dict[tuple[int, int, int], datetime] = {}
    weeks: dict[tuple[int, int], datetime] = {}
    for moment in sorted(moments, reverse=True):
        day = (moment.year, moment.month, moment.day)
        week = moment.isocalendar()[:2]
        if day not in days and len(days) < daily:
            days[day] = moment
        if week not in weeks and len(weeks) < weekly:
            weeks[week] = moment
    keep.update(days.values(), weeks.values())
    if moments:
        keep.add(max(moments))
    return keep


@dataclass(frozen=True, slots=True)
class Manifest:
    """What a backup holds, and what was checked of it. `counts` are rows by block, and by
    workspace inside each block: what a restore will show before it acts."""

    created_at: str  # ISO 8601, UTC
    reason: str  # "scheduled", "manual", "startup", "before-restore"
    otlet_version: str
    schema_revision: str
    encrypted: bool
    key_id: str | None  # which key encrypted it: files of backups with the same key are shared
    database_sha256: str  # of the stored file (encrypted or not)
    database_bytes: int
    files: int
    files_bytes: int
    files_new: int  # not already in an earlier backup: the cost of this one
    secrets: bool
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    duration_seconds: float = 0.0
    verified: bool = False
    problems: tuple[str, ...] = ()
    format: int = FORMAT_VERSION

    def to_json(self) -> str:
        data = asdict(self)
        data["problems"] = list(self.problems)
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "Manifest":
        data: dict[str, Any] = json.loads(text)
        data["problems"] = tuple(data.get("problems", ()))
        known = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in known})


@dataclass(frozen=True, slots=True)
class Schedule:
    """When the instance backs itself up (Réglages › Sauvegardes): once a day, at an hour in
    UTC (the interface shows it in the administrator's time), and how many are kept."""

    enabled: bool = True
    hour_utc: int = 2
    daily: int = DAILY
    weekly: int = WEEKLY


def due(now: datetime, last: datetime | None, schedule: Schedule) -> bool:
    """Whether the daily backup is due: past its hour, and none taken since that hour today.
    A day missed while Otlet was stopped is caught up once, at the next check."""
    if not schedule.enabled:
        return False
    now = now.astimezone(UTC)
    slot = now.replace(hour=schedule.hour_utc, minute=0, second=0, microsecond=0)
    if now < slot:
        slot -= timedelta(days=1)
    return last is None or last.astimezone(UTC) < slot
