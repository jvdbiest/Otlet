# SPDX-License-Identifier: AGPL-3.0-or-later
"""The interface's API types are generated from the current specification (X01)."""

from pathlib import Path

from otlet.entrypoints import cli

SNAPSHOT = Path(__file__).resolve().parents[3] / "frontend" / "src" / "api" / "openapi.json"


def test_the_interface_knows_the_current_api() -> None:
    assert SNAPSHOT.read_text(encoding="utf-8").strip() == cli.openapi_document().strip(), (
        "the API changed: run sh tools/generate-api-types.sh and commit the result"
    )


def test_schema_names_are_unique_across_routers() -> None:
    """Two response models of the same name would share one OpenAPI schema, and the interface
    would get the wrong type for one of them (it happened to CheckView)."""
    import inspect

    from pydantic import BaseModel

    from otlet.entrypoints.api import ai, auth, collection, triage, watch, workspaces

    names: dict[str, str] = {}
    for module in (ai, auth, collection, triage, watch, workspaces):
        for name, value in inspect.getmembers(module, inspect.isclass):
            if issubclass(value, BaseModel) and value.__module__ == module.__name__:
                assert name not in names, f"{name} in {names.get(name)} and {module.__name__}"
                names[name] = module.__name__
