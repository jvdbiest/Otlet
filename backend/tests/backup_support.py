# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared by the tests of the backups (tests/backup)."""

from pathlib import Path


class FakeDatabase:
    """A database whose dump is its current content, a few bytes."""

    def __init__(self) -> None:
        self.content = b"PGDMP database v1"
        self.restored: list[bytes] = []

    def dump(self, target: Path) -> None:
        target.write_bytes(self.content)

    def check(self, dump: Path) -> bool:
        return dump.read_bytes().startswith(b"PGDMP")

    def restore(self, dump: Path) -> None:
        self.restored.append(dump.read_bytes())
        self.content = dump.read_bytes()

    def schema_revision(self) -> str:
        return "0035"

    def counts(self) -> dict[str, dict[str, int]]:
        return {"briefs": {"w1": 3}}
