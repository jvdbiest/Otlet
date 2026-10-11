# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run inside a container (stdin of `python -`): look for any private key the process could
use, in the environment and on the whole file system, and try each one on the sealed
secret named in argv[1]. Prints a JSON report; exit code 0 if the secret could be opened.
Part of S6, criterion C3 (docs/spikes/S6.md §3.5)."""

import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from otlet.platform import database
from otlet.platform.config import Settings
from otlet.platform.secrets import SecretError, opening, store

SKIPPED = ("/proc", "/sys", "/dev")
MARKER = b"PRIVATE KEY-----"

name = sys.argv[1]
settings = Settings.from_env()
sealed = store.get(database.create_engine(settings.require_database_url()), name)
assert sealed is not None, f"no secret named {name}"

candidates: list[tuple[str, bytes]] = [
    (f"env:{key}", value.encode()) for key, value in os.environ.items() if MARKER.decode() in value
]
scanned = 0
for directory, subdirectories, files in os.walk("/"):
    if directory.startswith(SKIPPED):
        subdirectories.clear()
        continue
    for file in files:
        path = Path(directory) / file
        try:
            if not path.is_file() or path.stat().st_size > 1_000_000:
                continue
            content = path.read_bytes()
        except OSError:
            continue
        scanned += 1
        if MARKER in content:
            candidates.append((str(path), content))

opened_with = None
for origin, content in candidates:
    try:
        key = serialization.load_pem_private_key(content, password=None)
        opening.open_sealed(key, sealed, store.context(name))  # type: ignore[arg-type]
    except (ValueError, TypeError, SecretError, AttributeError):
        continue
    opened_with = origin
    break

print(
    json.dumps(
        {
            "files_scanned": scanned,
            "private_key_candidates": [origin for origin, _ in candidates],
            "opened_with": opened_with,
        }
    )
)
sys.exit(0 if opened_with else 1)
