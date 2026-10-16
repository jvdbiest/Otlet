# SPDX-License-Identifier: AGPL-3.0-or-later
"""The interface's API types are generated from the current specification (X01)."""

from pathlib import Path

from otlet.entrypoints import cli

SNAPSHOT = Path(__file__).resolve().parents[3] / "frontend" / "src" / "api" / "openapi.json"


def test_the_interface_knows_the_current_api() -> None:
    assert SNAPSHOT.read_text(encoding="utf-8").strip() == cli.openapi_document().strip(), (
        "the API changed: run sh tools/generate-api-types.sh and commit the result"
    )
