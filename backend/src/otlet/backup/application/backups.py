# SPDX-License-Identifier: AGPL-3.0-or-later
"""Taking, checking, keeping and restoring backups (F08, ADR-0042). A backup is written in a
hidden folder and appears under its name only once complete and checked: a backup cut short
never looks like a backup."""

import hashlib
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Protocol

from otlet.backup.domain.backup import (
    DAILY,
    DATABASE,
    ENCRYPTED,
    FILES,
    MANIFEST,
    SECRETS,
    WEEKLY,
    Manifest,
    kept,
    moment_of,
    name_of,
)


class Database(Protocol):
    def dump(self, target: Path) -> None:
        """A complete, consistent copy of the database, in PostgreSQL's custom format."""
        ...

    def check(self, dump: Path) -> bool:
        """Whether the copy reads back (its table of contents)."""
        ...

    def restore(self, dump: Path) -> None:
        """Replaces the whole database with the copy."""
        ...

    def schema_revision(self) -> str: ...

    def counts(self) -> dict[str, dict[str, int]]:
        """Rows by block, and by workspace inside each block."""
        ...


class Sealer(Protocol):
    key_id: str

    def seal(self, source: BinaryIO, target: BinaryIO) -> None: ...

    def open(self, source: BinaryIO, target: BinaryIO) -> None: ...


class BackupError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path) -> Iterator[Path]:
    """The files of the médiathèque, by their path under its root, in a stable order."""
    if root.exists():
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                yield path.relative_to(root)


class Catalog:
    """The backups of a destination, read only: what the administration screen lists."""

    def __init__(self, destination: Path) -> None:
        self._destination = destination

    def names(self) -> list[str]:
        """The complete backups, most recent first."""
        if not self._destination.exists():
            return []
        found = [
            path.name
            for path in self._destination.iterdir()
            if path.is_dir() and moment_of(path.name) is not None and (path / MANIFEST).exists()
        ]
        return sorted(found, reverse=True)

    def manifest(self, name: str) -> Manifest:
        return Manifest.from_json((self.folder(name) / MANIFEST).read_text("utf-8"))

    def folder(self, name: str) -> Path:
        if moment_of(name) is None:
            raise BackupError(f"not a backup name: {name}")
        folder = self._destination / name
        if not (folder / MANIFEST).exists():
            raise BackupError(f"no such backup: {name}")
        return folder


class Backups(Catalog):
    def __init__(
        self,
        destination: Path,
        database: Database,
        files_dir: Path,
        sealer: Sealer | None,
        secrets: tuple[Path, ...] = (),
        otlet_version: str = "dev",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(destination)
        self._database = database
        self._files_dir = files_dir
        self._sealer = sealer
        self._secrets = secrets
        self._version = otlet_version
        self._clock = clock

    # -- Taking ----------------------------------------------------------------------------

    def run(self, reason: str) -> str:
        """Takes a backup: the database, the files (shared with the previous backup made with
        the same key), the secrets if encrypted, the manifest; then checks it. Its name."""
        started = time.monotonic()
        moment = self._clock() if self._clock else datetime.now().astimezone()
        self._destination.mkdir(parents=True, exist_ok=True)
        while (self._destination / name_of(moment)).exists():
            moment += timedelta(seconds=1)  # two in the same second: a restore's own backup
        name = name_of(moment)
        partial = Path(tempfile.mkdtemp(prefix=f".partial-{name}-", dir=self._destination))
        partial.chmod(0o755)  # readable by the API, which lists and downloads the backups
        try:
            suffix = ENCRYPTED if self._sealer else ""
            with tempfile.TemporaryDirectory(dir=self._destination, prefix=".dump-") as scratch:
                plain = Path(scratch) / DATABASE
                self._database.dump(plain)
                stored = partial / (DATABASE + suffix)
                self._store(plain, stored)
            files, files_bytes, new = self._copy_files(partial / FILES)
            secrets = self._copy_secrets(partial / SECRETS)
            manifest = Manifest(
                created_at=moment.isoformat(),
                reason=reason,
                otlet_version=self._version,
                schema_revision=self._database.schema_revision(),
                encrypted=self._sealer is not None,
                key_id=self._sealer.key_id if self._sealer else None,
                database_sha256=_sha256(stored),
                database_bytes=stored.stat().st_size,
                files=files,
                files_bytes=files_bytes,
                files_new=new,
                secrets=secrets,
                counts=self._database.counts(),
            )
            problems = self._check(partial, manifest, only_new=True)
            manifest = replace(
                manifest,
                duration_seconds=round(time.monotonic() - started, 1),
                verified=not problems,
                problems=tuple(problems),
            )
            (partial / MANIFEST).write_text(manifest.to_json(), "utf-8")
            partial.rename(self._destination / name)
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise
        return name

    def _store(self, source: Path, target: Path) -> None:
        if self._sealer is None:
            shutil.copyfile(source, target)
            return
        with source.open("rb") as plain, target.open("wb") as sealed:
            self._sealer.seal(plain, sealed)

    def _previous_files(self) -> Path | None:
        """The files of the latest backup made with the same key, to share them."""
        key = self._sealer.key_id if self._sealer else None
        for name in self.names():
            if self.manifest(name).key_id == key:
                return self._destination / name / FILES
        return None

    def _copy_files(self, target: Path) -> tuple[int, int, int]:
        """Each file once: a file already in the previous backup is linked, not copied (a
        content-addressed file never changes). Where links are not possible, it is copied."""
        target.mkdir()
        previous = self._previous_files()
        suffix = ENCRYPTED if self._sealer else ""
        count = size = new = 0
        for relative in _files(self._files_dir):
            source = self._files_dir / relative
            stored = target / (str(relative) + suffix)
            stored.parent.mkdir(parents=True, exist_ok=True)
            earlier = None if previous is None else previous / (str(relative) + suffix)
            if earlier is not None and earlier.exists():
                try:
                    os.link(earlier, stored)
                except OSError:
                    shutil.copyfile(earlier, stored)
            else:
                self._store(source, stored)
                new += 1
            count += 1
            size += source.stat().st_size
        return count, size, new

    def _copy_secrets(self, target: Path) -> bool:
        """The secrets of the instance, only in an encrypted backup (ADR-0042)."""
        present = [path for path in self._secrets if path.is_file()]
        if self._sealer is None or not present:
            return False
        target.mkdir()
        for path in present:
            self._store(path, target / (path.name + ENCRYPTED))
        return True

    # -- Checking --------------------------------------------------------------------------

    def verify(self, name: str) -> list[str]:
        """Checks a whole backup again: what is wrong with it, if anything."""
        folder = self.folder(name)
        return self._check(folder, self.manifest(name), only_new=False)

    def _check(self, folder: Path, manifest: Manifest, only_new: bool) -> list[str]:
        problems: list[str] = []
        suffix = ENCRYPTED if manifest.encrypted else ""
        stored = folder / (DATABASE + suffix)
        if _sha256(stored) != manifest.database_sha256:
            problems.append("database: checksum differs")
        with tempfile.TemporaryDirectory(dir=self._destination, prefix=".check-") as scratch:
            plain = Path(scratch) / DATABASE
            try:
                self._open(stored, plain, manifest)
                if not self._database.check(plain):
                    problems.append("database: the copy does not read back")
            except BackupError as error:
                problems.append(f"database: {error}")
        files = folder / FILES
        for path in sorted(files.rglob("*")) if files.exists() else []:
            if not path.is_file():
                continue
            if only_new and path.stat().st_nlink > 1:
                continue  # shared with an earlier backup, checked when it was written
            expected = path.name.removesuffix(suffix).split(".")[0]
            if len(expected) != 64:
                continue  # not addressed by its content: nothing to compare
            with tempfile.TemporaryDirectory(dir=self._destination, prefix=".check-") as scratch:
                plain = Path(scratch) / "file"
                try:
                    self._open(path, plain, manifest)
                except BackupError as error:
                    problems.append(f"{path.relative_to(folder)}: {error}")
                    continue
                if _sha256(plain) != expected:
                    problems.append(f"{path.relative_to(folder)}: content differs from its name")
        return problems

    def _open(self, stored: Path, plain: Path, manifest: Manifest) -> None:
        if not manifest.encrypted:
            shutil.copyfile(stored, plain)
            return
        if self._sealer is None or self._sealer.key_id != manifest.key_id:
            raise BackupError("encrypted with another passphrase")
        try:
            with stored.open("rb") as sealed, plain.open("wb") as target:
                self._sealer.open(sealed, target)
        except ValueError as error:
            raise BackupError(str(error)) from error

    # -- Keeping ---------------------------------------------------------------------------

    def prune(self, daily: int = DAILY, weekly: int = WEEKLY) -> list[str]:
        """Removes the backups no longer kept; the names removed. Shared files survive in the
        backups that still link them."""
        names = self.names()
        moments = {name: moment_of(name) for name in names}
        keep = kept([m for m in moments.values() if m is not None], daily, weekly)
        removed = [name for name, moment in moments.items() if moment not in keep]
        for name in removed:
            shutil.rmtree(self._destination / name)
        return removed

    # -- Restoring -------------------------------------------------------------------------

    def _give_back(self, target: Path) -> None:
        """A restored file belongs to the owner of the médiathèque, like the others: the
        backup service may run as another user (root, to reach any destination)."""
        euid, chown = getattr(os, "geteuid", None), getattr(os, "chown", None)
        if euid is None or chown is None or euid() != 0:
            return
        owner = self._files_dir.stat()
        for path in (target, *target.relative_to(self._files_dir).parents):
            full = path if path.is_absolute() else self._files_dir / path
            if full != self._files_dir:
                chown(full, owner.st_uid, owner.st_gid)

    def restore(self, name: str, secrets_to: Path | None = None) -> str:
        """Replaces the database and adds back the missing or damaged files of the
        médiathèque, after a backup of the current state (ADR-0042): the name of that one.
        The secrets are written to `secrets_to` only when asked."""
        folder = self.folder(name)
        manifest = self.manifest(name)
        problems = self._check(folder, manifest, only_new=False)
        if problems:
            raise BackupError("the backup does not check: " + "; ".join(problems[:3]))
        safety = self.run("before-restore")
        suffix = ENCRYPTED if manifest.encrypted else ""
        with tempfile.TemporaryDirectory(dir=self._destination, prefix=".restore-") as scratch:
            plain = Path(scratch) / DATABASE
            self._open(folder / (DATABASE + suffix), plain, manifest)
            self._database.restore(plain)
        files = folder / FILES
        for path in sorted(files.rglob("*")) if files.exists() else []:
            if not path.is_file():
                continue
            relative = Path(str(path.relative_to(files)).removesuffix(suffix))
            target = self._files_dir / relative
            expected = relative.name.split(".")[0]
            if target.exists() and (len(expected) != 64 or _sha256(target) == expected):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            self._open(path, target, manifest)
            self._give_back(target)
        if secrets_to is not None and manifest.secrets:
            secrets_to.mkdir(parents=True, exist_ok=True)
            for path in sorted((folder / SECRETS).iterdir()):
                self._open(path, secrets_to / path.name.removesuffix(ENCRYPTED), manifest)
        return safety
