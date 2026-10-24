# SPDX-License-Identifier: AGPL-3.0-or-later
"""The backup service (ADR-0042): the daily backup when due, « Sauvegarder maintenant », a
destination it cannot write to; and Réglages › Sauvegardes for the administrator only."""

import io
import tarfile
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backup_support import FakeDatabase
from integration_support import TestDatabase, requires_database
from otlet.backup.adapters.archive import tar_stream
from otlet.backup.application.backups import Backups
from otlet.backup.application.service import BackupService, Request, State
from otlet.backup.domain.backup import Schedule, due
from otlet.entrypoints import cli
from otlet.entrypoints.api.app import create_app
from otlet.entrypoints.api.auth import CSRF_HEADER
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.platform.config import Settings

NIGHT = datetime(2026, 10, 23, 1, 30, tzinfo=UTC)


def test_the_daily_backup_is_due_once_past_its_hour() -> None:
    schedule = Schedule(hour_utc=2)
    assert not due(NIGHT, NIGHT - timedelta(hours=10), schedule)  # before 2:00, yesterday's
    assert due(NIGHT, NIGHT - timedelta(days=1, hours=1), schedule)  # yesterday's was missed
    after = NIGHT + timedelta(hours=1)
    assert due(after, NIGHT, schedule) and not due(after, after, schedule)
    assert due(after, None, schedule)
    assert not due(after, None, replace(schedule, enabled=False))


class MemoryControl:
    def __init__(self) -> None:
        self.saved_schedule = Schedule(hour_utc=2)
        self.saved_request: Request | None = None
        self.saved_state = State()

    def schedule(self) -> Schedule:
        return self.saved_schedule

    def save_schedule(self, schedule: Schedule) -> None:
        self.saved_schedule = schedule

    def request(self) -> Request | None:
        return self.saved_request

    def save_request(self, request: Request) -> None:
        self.saved_request = request

    def state(self) -> State:
        return self.saved_state

    def save_state(self, state: State) -> None:
        self.saved_state = state


def test_the_service_backs_up_when_due_or_asked(tmp_path: Path) -> None:
    destination = tmp_path / "dest"
    clock = [NIGHT + timedelta(hours=1)]
    backups = Backups(destination, FakeDatabase(), tmp_path / "files", None, clock=lambda: clock[0])
    control = MemoryControl()
    service = BackupService(backups, destination, control, False, lambda: clock[0])
    first = service.step()
    assert first is not None and backups.manifest(first).reason == "scheduled"
    assert control.saved_state.writable and control.saved_state.last_name == first
    assert service.step() is None  # done for today
    control.save_request(Request(NIGHT.isoformat(), "admin", "pending"))
    clock[0] += timedelta(minutes=5)
    second = service.step()
    assert second is not None and backups.manifest(second).reason == "manual"
    assert control.saved_request is not None and control.saved_request.status == "done"


def test_a_destination_it_cannot_write_to_is_reported(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("a file, not a folder")
    backups = Backups(blocked, FakeDatabase(), tmp_path / "files", None)
    control = MemoryControl()
    control.save_request(Request(NIGHT.isoformat(), "admin", "pending"))
    assert BackupService(backups, blocked, control, False).step() is None
    assert not control.saved_state.writable and control.saved_state.error
    assert control.saved_request is not None and control.saved_request.status == "failed"


def test_a_backup_downloads_as_one_tar(tmp_path: Path) -> None:
    folder = tmp_path / "2026-10-23T020000Z"
    (folder / "files" / "ab").mkdir(parents=True)
    (folder / "manifest.json").write_text("{}")
    (folder / "files" / "ab" / "x.png").write_bytes(b"x" * 1000)
    archive = tarfile.open(fileobj=io.BytesIO(b"".join(tar_stream(folder))))
    assert sorted(archive.getnames()) == [
        "2026-10-23T020000Z/files/ab/x.png",
        "2026-10-23T020000Z/manifest.json",
    ]
    member = archive.extractfile("2026-10-23T020000Z/files/ab/x.png")
    assert member is not None and member.read() == b"x" * 1000


LOGIN = "admin@example.org"
PASSWORD = "une phrase de passe assez longue"  # noqa: S105 (test account)


@pytest.fixture
def admin_client(
    migrated: TestDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[tuple[TestClient, dict[str, str], Path]]:
    monkeypatch.setenv("OTLET_DATABASE_URL", migrated.app_url)
    monkeypatch.setenv("OTLET_RUN_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO(PASSWORD + "\n"))
    assert cli.main(["admin", "create", "--login", LOGIN, "--name", "Admin"]) == 0
    destination = tmp_path / "backups"
    backups = Backups(destination, FakeDatabase(), tmp_path / "files", None)
    backups.run("manual")
    settings = Settings(
        ui_dir=None, run_dir=tmp_path, database_url=migrated.app_url, backup_dir=destination
    )
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        response = client.post("/api/auth/login", json={"login": LOGIN, "password": PASSWORD})
        yield client, {CSRF_HEADER: response.json()["csrf_token"]}, destination


@requires_database
def test_the_administrator_sees_schedules_and_asks_for_backups(
    admin_client: tuple[TestClient, dict[str, str], Path], migrated: TestDatabase
) -> None:
    client, headers, _ = admin_client
    overview = client.get("/api/admin/backups").json()
    assert overview["state"]["configured"] is True
    (backup,) = overview["backups"]
    assert backup["verified"] and backup["totals"] == {"briefs": 3}
    schedule = {"enabled": True, "hour_utc": 3, "daily": 10, "weekly": 6}
    assert client.put("/api/admin/backups/schedule", json=schedule, headers=headers).json() == (
        schedule
    )
    assert client.get("/api/admin/backups").json()["schedule"] == schedule
    assert client.post("/api/admin/backups/run", headers=headers).status_code == 202
    assert client.post("/api/admin/backups/run", headers=headers).status_code == 409
    download = client.get(f"/api/admin/backups/{backup['name']}/download")
    assert download.status_code == 200
    assert tarfile.open(fileobj=io.BytesIO(download.content)).getnames()
    assert client.get("/api/admin/backups/../etc/download").status_code == 404
    assert client.get("/api/admin/backups/not-a-name/download").status_code == 404
    # Anyone else is refused.
    engine = db.create_engine(migrated.app_url)
    Authentication(PostgresIdentityStore(engine), Argon2Hasher()).create_user(
        "Eve", "eve@example.org", PASSWORD
    )
    client.post("/api/auth/logout", headers=headers)
    client.post("/api/auth/login", json={"login": "eve@example.org", "password": PASSWORD})
    assert client.get("/api/admin/backups").status_code == 403
