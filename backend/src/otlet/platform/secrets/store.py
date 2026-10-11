# SPDX-License-Identifier: AGPL-3.0-or-later
"""Storage of sealed secrets. Until the modules that own secrets exist (É1), they live in
instance_settings under `secret:<name>`; the sealed bytes are never readable as plaintext."""

import base64
import json

import sqlalchemy as sa

PREFIX = "secret:"


def context(name: str) -> bytes:
    """Associated data binding a sealed value to its name."""
    return f"{PREFIX}{name}".encode()


def put(engine: sa.Engine, name: str, sealed: bytes) -> None:
    value = json.dumps({"sealed": base64.b64encode(sealed).decode("ascii")})
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO instance_settings (key, value) VALUES (:key, CAST(:value AS jsonb))"
                " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()"
            ),
            {"key": f"{PREFIX}{name}", "value": value},
        )


def get(engine: sa.Engine, name: str) -> bytes | None:
    with engine.connect() as connection:
        value = connection.execute(
            sa.text("SELECT value ->> 'sealed' FROM instance_settings WHERE key = :key"),
            {"key": f"{PREFIX}{name}"},
        ).scalar()
    return None if value is None else base64.b64decode(value)
