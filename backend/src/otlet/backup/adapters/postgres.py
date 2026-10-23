# SPDX-License-Identifier: AGPL-3.0-or-later
"""The database side of a backup, with PostgreSQL's own tools (pg_dump, pg_restore) and the
owner role: the role of the application cannot see past row-level security, so it could not
copy the whole instance, and must not be able to replace it (M-12, ADR-0042)."""

import subprocess  # noqa: S404 — the PostgreSQL client tools, called with fixed arguments
from pathlib import Path

import sqlalchemy as sa

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
        """The whole database replaced in one transaction: all or nothing."""
        done = self._run(
            "pg_restore",
            "--clean",
            "--if-exists",
            "--single-transaction",
            "--exit-on-error",
            f"--dbname={self._url}",
            str(dump),
        )
        if done.returncode != 0:
            raise RuntimeError("pg_restore: " + done.stderr.decode(errors="replace").strip())

    def schema_revision(self) -> str:
        with self._engine.connect() as connection:
            found = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        return str(found or "")

    def counts(self) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {}
        with self._engine.connect() as connection:
            for block, table in BLOCKS.items():
                rows = connection.execute(
                    sa.text(f"SELECT workspace_id, count(*) FROM {table} GROUP BY workspace_id")  # noqa: S608 — fixed names
                ).all()
                counts[block] = {str(row[0]): int(row[1]) for row in rows}
        return counts
