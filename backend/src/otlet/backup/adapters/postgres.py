# SPDX-License-Identifier: AGPL-3.0-or-later
"""The database side of a backup, with PostgreSQL's own tools (pg_dump, pg_restore) and the
owner role: the role of the application cannot see past row-level security, so it could not
copy the whole instance, and must not be able to replace it (M-12, ADR-0042)."""

import subprocess  # noqa: S404 — the PostgreSQL client tools, called with fixed arguments
import tempfile
from pathlib import Path

import sqlalchemy as sa

# Before the copy is replayed: the schema emptied, in the same transaction (all or nothing).
RESET = b"SET client_min_messages = warning;\nDROP SCHEMA public CASCADE;\nCREATE SCHEMA public;\n"

# The blocks a restore will name (ADR-0042), counted by workspace in each manifest.
BLOCKS = {
    "sources": "sources",
    "items": "source_items",
    "topics": "topics",
    "briefs": "briefs",
    "articles": "articles",
    "versions": "article_versions",
    "media": "media",
}


class PostgresDatabase:
    def __init__(self, url: str) -> None:
        """`url`: postgresql://owner:password@host:port/database, for the client tools."""
        self._url = url
        self._engine = sa.create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(  # noqa: S603 — fixed program, no shell
            arguments, capture_output=True, check=False, timeout=6 * 3600
        )

    def dump(self, target: Path) -> None:
        done = self._run("pg_dump", "--format=custom", f"--file={target}", f"--dbname={self._url}")
        if done.returncode != 0:
            raise RuntimeError("pg_dump: " + done.stderr.decode(errors="replace").strip())

    def check(self, dump: Path) -> bool:
        return self._run("pg_restore", "--list", str(dump)).returncode == 0

    def restore(self, dump: Path) -> None:
        """The whole database replaced in one transaction, all or nothing: the schema emptied,
        then the copy replayed, with its owners and grants (the roles of M-12 exist)."""
        with tempfile.TemporaryFile() as errors:
            restore = ("pg_restore", "--file=-", str(dump))
            reader = subprocess.Popen(restore, stdout=subprocess.PIPE, stderr=errors)  # noqa: S603
            replay = (
                "psql",
                "--quiet",
                "--single-transaction",
                "--set=ON_ERROR_STOP=1",
                f"--dbname={self._url}",
            )
            writer = subprocess.Popen(  # noqa: S603 — fixed programs, no shell
                replay,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=errors,
            )
            source, sink = reader.stdout, writer.stdin
            if source is None or sink is None:
                raise RuntimeError("restore: no pipe")
            sink.write(RESET)
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                sink.write(chunk)
            sink.close()
            if reader.wait() != 0 or writer.wait() != 0:
                errors.seek(0)
                message = errors.read().decode(errors="replace").strip()
                raise RuntimeError("restore: " + message[-2000:])

    def schema_revision(self) -> str:
        """The migration of the database; empty before the very first one (a new instance)."""
        with self._engine.connect() as connection:
            if (
                connection.execute(sa.text("SELECT to_regclass('alembic_version')")).scalar()
                is None
            ):
                return ""
            found = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        return str(found or "")

    def counts(self) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {}
        with self._engine.connect() as connection:
            for block, table in BLOCKS.items():
                exists = connection.execute(sa.text("SELECT to_regclass(:t)"), {"t": table})
                if exists.scalar() is None:
                    continue  # not created yet: a new instance, before its migrations
                rows = connection.execute(
                    sa.text(f"SELECT workspace_id, count(*) FROM {table} GROUP BY workspace_id")  # noqa: S608 — fixed names
                ).all()
                counts[block] = {str(row[0]): int(row[1]) for row in rows}
        return counts
