# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deployment settings, read from the environment only (ARCHITECTURE §20.3)."""

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    ui_dir: Path | None
    run_dir: Path

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        ui_dir = env.get("OTLET_UI_DIR")
        run_dir = env.get("OTLET_RUN_DIR") or str(Path(tempfile.gettempdir()) / "otlet")
        return cls(ui_dir=Path(ui_dir) if ui_dir else None, run_dir=Path(run_dir))
