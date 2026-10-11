# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deployment settings, read from the environment only (ARCHITECTURE §20.3)."""

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# backend/migrations in a source checkout; the image sets OTLET_MIGRATIONS_DIR.
SOURCE_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


@dataclass(frozen=True, slots=True)
class Settings:
    ui_dir: Path | None
    run_dir: Path
    database_url: str | None = None
    migrations_dir: Path = SOURCE_MIGRATIONS_DIR

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        ui_dir = env.get("OTLET_UI_DIR")
        run_dir = env.get("OTLET_RUN_DIR") or str(Path(tempfile.gettempdir()) / "otlet")
        migrations_dir = env.get("OTLET_MIGRATIONS_DIR")
        return cls(
            ui_dir=Path(ui_dir) if ui_dir else None,
            run_dir=Path(run_dir),
            database_url=env.get("OTLET_DATABASE_URL") or None,
            migrations_dir=Path(migrations_dir) if migrations_dir else SOURCE_MIGRATIONS_DIR,
        )

    def require_database_url(self) -> str:
        if self.database_url is None:
            raise RuntimeError("OTLET_DATABASE_URL is not set")
        return self.database_url
