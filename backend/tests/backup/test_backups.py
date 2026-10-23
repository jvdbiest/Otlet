# SPDX-License-Identifier: AGPL-3.0-or-later
"""Backups (F08, ADR-0042): complete copies, files shared between backups, encryption, checks,
what is kept, and a restore that takes a backup first."""

import io
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backup_support import FakeDatabase
from otlet.backup.adapters.crypto import CHUNK, Cipher, WrongPassphrase
from otlet.backup.application.backups import BackupError, Backups
from otlet.backup.domain.backup import Manifest, kept, moment_of, name_of

SHA = "a" * 64


def media(root: Path, data: bytes, extension: str = "png") -> Path:
    import hashlib

    sha = hashlib.sha256(data).hexdigest()
    path = root / sha[:2] / sha[2:4] / f"{sha}.{extension}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 23, 20, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


def backups(tmp_path: Path, passphrase: str | None, clock: Clock | None = None) -> Backups:
    destination = tmp_path / "dest"
    destination.mkdir(exist_ok=True)
    secrets = tmp_path / "keys"
    secrets.mkdir(exist_ok=True)
    (secrets / "secrets-private.pem").write_text("PRIVATE KEY")
    sealer = Cipher.for_destination(destination, passphrase) if passphrase else None
    return Backups(
        destination,
        DATABASE,
        tmp_path / "files",
        sealer,
        (secrets / "secrets-private.pem",),
        "test",
        clock or Clock(),
    )


DATABASE = FakeDatabase()


def test_names_and_what_is_kept() -> None:
    moment = datetime(2026, 10, 23, 20, 15, 5, tzinfo=UTC)
    assert name_of(moment) == "2026-10-23T201505Z" and moment_of(name_of(moment)) == moment
    assert moment_of("keyring.json") is None
    days = [datetime(2026, 10, 23, tzinfo=UTC) - timedelta(days=n) for n in range(40)]
    later = days[0] + timedelta(hours=2)  # two the same day: the latest is kept
    keep = kept([*days, later], daily=7, weekly=4)
    assert later in keep and set(days[1:7]) <= keep and days[0] not in keep
    assert len(keep) <= 7 + 4 and days[-1] not in keep
    assert kept([days[-1]], 0, 0) == {days[-1]}  # the latest always stays


def test_sealing_by_chunks(tmp_path: Path) -> None:
    cipher = Cipher.for_destination(tmp_path, "une phrase de passe")
    again = Cipher.for_destination(tmp_path, "une phrase de passe")
    assert cipher.key_id == again.key_id  # the salt is kept beside the backups
    assert Cipher.for_destination(tmp_path, "une autre").key_id != cipher.key_id
    for data in (b"", b"court", os.urandom(CHUNK * 2 + 17), os.urandom(CHUNK)):
        sealed, plain = io.BytesIO(), io.BytesIO()
        cipher.seal(io.BytesIO(data), sealed)
        assert data == b"" or data not in sealed.getvalue()
        again.open(io.BytesIO(sealed.getvalue()), plain)
        assert plain.getvalue() == data
    sealed = io.BytesIO()
    cipher.seal(io.BytesIO(os.urandom(CHUNK + 5)), sealed)
    with pytest.raises(WrongPassphrase):
        Cipher.for_destination(tmp_path, "une autre").open(
            io.BytesIO(sealed.getvalue()), io.BytesIO()
        )
    cut = sealed.getvalue()[: CHUNK + 16 + 16]  # the last chunk lost: refused, not shortened
    with pytest.raises(WrongPassphrase):
        cipher.open(io.BytesIO(cut), io.BytesIO())


@pytest.mark.parametrize("passphrase", [None, "une phrase de passe assez longue"])
def test_a_backup_holds_the_database_the_files_and_a_checked_manifest(
    tmp_path: Path, passphrase: str | None
) -> None:
    files = tmp_path / "files"
    first = media(files, b"image une")
    service = backups(tmp_path, passphrase)
    name = service.run("manual")
    manifest = service.manifest(name)
    assert manifest.verified and manifest.problems == ()
    assert (manifest.files, manifest.files_new, manifest.counts) == (1, 1, {"briefs": {"w1": 3}})
    assert manifest.encrypted is (passphrase is not None)
    assert manifest.secrets is (passphrase is not None)  # secrets only when encrypted
    folder = tmp_path / "dest" / name
    stored = folder / "files" / first.relative_to(files)
    if passphrase:
        assert (
            not stored.exists()
            and b"image une" not in stored.with_name(stored.name + ".enc").read_bytes()
        )
    else:
        assert stored.read_bytes() == b"image une"
    # A second backup shares the unchanged file and copies only the new one.
    media(files, b"image deux")
    second = service.run("scheduled")
    again = service.manifest(second)
    assert (again.files, again.files_new, again.verified) == (2, 1, True)
    suffix = ".enc" if passphrase else ""
    shared = tmp_path / "dest" / second / "files" / (str(first.relative_to(files)) + suffix)
    assert shared.stat().st_nlink == 2
    assert service.names() == [second, name]
    assert Manifest.from_json(again.to_json()) == again


def test_a_damaged_backup_does_not_check(tmp_path: Path) -> None:
    media(tmp_path / "files", b"image")
    service = backups(tmp_path, "une phrase de passe assez longue")
    name = service.run("manual")
    assert service.verify(name) == []
    damaged = next((tmp_path / "dest" / name / "files").rglob("*.enc"))
    damaged.write_bytes(damaged.read_bytes()[:-3] + b"xyz")
    problems = service.verify(name)
    assert len(problems) == 1 and "files" in problems[0]
    with pytest.raises(BackupError):
        service.restore(name)
    other = Backups(
        tmp_path / "dest",
        DATABASE,
        tmp_path / "files",
        Cipher.for_destination(tmp_path / "dest", "une autre phrase"),
    )
    assert any("another passphrase" in p for p in other.verify(name))


def test_a_restore_takes_a_backup_first_then_brings_everything_back(tmp_path: Path) -> None:
    files = tmp_path / "files"
    kept_file = media(files, b"image gardee")
    lost = media(files, b"image perdue")
    database = FakeDatabase()
    clock = Clock()
    service = backups(tmp_path, "une phrase de passe assez longue", clock)
    service._database = database  # noqa: SLF001 — this test's own database
    name = service.run("manual")
    # Then something goes wrong: the database changes, a file is lost, another is damaged.
    database.content = b"PGDMP database v2, broken"
    lost.unlink()
    kept_file.write_bytes(b"corrupted")
    restored_to = tmp_path / "restored-keys"
    safety = service.restore(name, restored_to)
    assert database.restored == [b"PGDMP database v1"]
    assert lost.read_bytes() == b"image perdue" and kept_file.read_bytes() == b"image gardee"
    assert (restored_to / "secrets-private.pem").read_text() == "PRIVATE KEY"
    assert service.manifest(safety).reason == "before-restore"  # the state before is kept
    assert set(service.names()) == {name, safety}


def test_old_backups_are_pruned(tmp_path: Path) -> None:
    clock = Clock()
    service = backups(tmp_path, None, clock)
    names = []
    for _ in range(3):
        names.append(service.run("scheduled"))
        clock.now += timedelta(days=1)
    removed = service.prune(daily=2, weekly=0)
    assert removed == [names[0]] and service.names() == [names[2], names[1]]
