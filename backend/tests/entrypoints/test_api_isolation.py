# SPDX-License-Identifier: AGPL-3.0-or-later
"""Isolation of the API (F03, ARCHITECTURE §8.1 point 3): "no context, zero rows" extended
from the database to every route.

These tests walk the routes of the application, so a new route is covered as soon as it exists:
- every /api route requires a session, except the few listed in PUBLIC_ROUTES;
- every route of a workspace checks the membership, and answers 404 to a non-member;
- without a session, every route answers 401; a member of workspace A gets 404 from every route
  of workspace B, whatever the method.
"""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from integration_support import TestDatabase, requires_database
from otlet.entrypoints.api.app import create_app
from otlet.entrypoints.api.auth import CSRF_HEADER
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.platform.config import Settings
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces

pytestmark = requires_database

# The only routes reachable without a session, each with its reason.
PUBLIC_ROUTES = {
    ("POST", "/api/auth/login"): "opens the session",
}
PASSWORD = "une phrase de passe assez longue"  # noqa: S105 (test accounts)
WORKSPACE_ROUTE = PREFIX + "/{workspace_id}"


@dataclass(frozen=True)
class World:
    app: FastAPI
    workspace_a: uuid.UUID
    workspace_b: uuid.UUID


def calls(dependant: Dependant) -> set[Callable[..., Any]]:
    """Every dependency a route runs, at any depth."""
    found: set[Callable[..., Any]] = set()
    for dependency in dependant.dependencies:
        if dependency.call is not None:
            found.add(dependency.call)
        found |= calls(dependency)
    return found


def api_routes(app: FastAPI) -> list[tuple[str, APIRoute]]:
    """The routes of the API routers (test_the_routers_cover_the_whole_api proves they are
    all the API), one entry per method."""
    return [
        (method, route)
        for router in app.state.api_routers
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in sorted(route.methods or ())
    ]


def test_the_routers_cover_the_whole_api(world: World) -> None:
    published = {
        (method.upper(), path)
        for path, operations in world.app.openapi()["paths"].items()
        if path.startswith("/api/")
        for method in operations
    }
    assert published == {(method, route.path) for method, route in api_routes(world.app)}


def fill(path: str, workspace_id: uuid.UUID) -> str:
    """The route's path with the given workspace and random identifiers for the rest."""
    filled = path.replace("{workspace_id}", str(workspace_id))
    while "{" in filled:
        start, end = filled.index("{"), filled.index("}")
        filled = filled[:start] + str(uuid.uuid4()) + filled[end + 1 :]
    return filled


@pytest.fixture
def world(migrated: TestDatabase, tmp_path: Path) -> World:
    """Alice owns workspace A, Bob owns workspace B."""
    engine = db.create_engine(migrated.app_url)
    authentication = Authentication(PostgresIdentityStore(engine), Argon2Hasher())
    workspaces = Workspaces(PostgresWorkspaceStore(engine))
    created = []
    for login in ("alice@example.org", "bob@example.org"):
        user = authentication.create_user(login.split("@")[0], login, PASSWORD)
        created.append(workspaces.create(user, f"Espace de {login}").id)
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=migrated.app_url)
    return World(app=create_app(settings), workspace_a=created[0], workspace_b=created[1])


@pytest.fixture
def alice(world: World) -> Iterator[tuple[TestClient, str]]:
    """A client signed in as Alice, with her CSRF token."""
    with TestClient(world.app, base_url="https://testserver") as client:
        response = client.post(
            "/api/auth/login", json={"login": "alice@example.org", "password": PASSWORD}
        )
        assert response.status_code == 200
        yield client, response.json()["csrf_token"]


def test_every_api_route_requires_a_session(world: World) -> None:
    session = world.app.state.current_session
    unprotected = {
        (method, route.path)
        for method, route in api_routes(world.app)
        if session not in calls(route.dependant)
    }
    assert unprotected == PUBLIC_ROUTES.keys()


def test_every_workspace_route_checks_the_membership(world: World) -> None:
    context = world.app.state.workspace_context
    workspace_routes = [
        (method, route)
        for method, route in api_routes(world.app)
        if route.path.startswith(PREFIX + "/")
    ]
    assert workspace_routes, "no workspace route found: the test would prove nothing"
    for method, route in workspace_routes:
        assert route.path.startswith(WORKSPACE_ROUTE), (method, route.path)
        assert context in calls(route.dependant), (method, route.path)


def test_without_a_session_every_route_answers_401(world: World) -> None:
    with TestClient(world.app, base_url="https://testserver") as client:
        for method, route in api_routes(world.app):
            if (method, route.path) in PUBLIC_ROUTES:
                continue
            response = client.request(method, fill(route.path, world.workspace_a), json={})
            assert response.status_code == 401, (method, route.path, response.text)


def test_a_member_gets_404_from_every_route_of_another_workspace(
    world: World, alice: tuple[TestClient, str]
) -> None:
    client, csrf = alice
    for method, route in api_routes(world.app):
        if not route.path.startswith(WORKSPACE_ROUTE):
            continue
        response = client.request(
            method, fill(route.path, world.workspace_b), json={}, headers={CSRF_HEADER: csrf}
        )
        assert response.status_code == 404, (method, route.path, response.text)
        # Same answer as for a workspace that does not exist.
        missing = client.request(
            method, fill(route.path, uuid.uuid4()), json={}, headers={CSRF_HEADER: csrf}
        )
        assert (missing.status_code, missing.json()) == (response.status_code, response.json())


def test_a_member_lists_and_enters_only_their_workspaces(
    world: World, alice: tuple[TestClient, str]
) -> None:
    client, _ = alice
    listed = client.get(PREFIX).json()
    assert [workspace["id"] for workspace in listed] == [str(world.workspace_a)]
    assert listed[0]["role"] == "owner"
    entered = client.get(f"{PREFIX}/{world.workspace_a}")
    assert entered.status_code == 200
    assert entered.json()["name"] == "Espace de alice@example.org"


def test_a_created_workspace_belongs_to_its_creator(
    world: World, alice: tuple[TestClient, str]
) -> None:
    client, csrf = alice
    response = client.post(PREFIX, json={"name": "  Veille   tech "}, headers={CSRF_HEADER: csrf})
    assert response.status_code == 201
    assert response.json()["name"] == "Veille tech"
    assert len(client.get(PREFIX).json()) == 2
