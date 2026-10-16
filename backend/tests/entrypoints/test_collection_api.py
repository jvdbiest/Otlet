# SPDX-License-Identifier: AGPL-3.0-or-later
"""The routes of sources and items on a real PostgreSQL (U01). The collection itself is tested
in tests/collection; here, what the API adds: validation, error codes, and the jobs it
enqueues in the same transaction."""

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from integration_support import TestDatabase, requires_database
from otlet.entrypoints import cli
from otlet.entrypoints.api.app import create_app
from otlet.entrypoints.api.auth import CSRF_HEADER
from otlet.platform import database as db
from otlet.platform.config import Settings

pytestmark = requires_database

LOGIN = "joel@example.org"
PASSWORD = "une phrase de passe assez longue"  # noqa: S105 (test account)


@pytest.fixture
def signed_in(
    migrated: TestDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[tuple[TestClient, dict[str, str], str]]:
    """A client signed in as the administrator, its CSRF header and its workspace prefix."""
    monkeypatch.setenv("OTLET_DATABASE_URL", migrated.app_url)
    monkeypatch.setenv("OTLET_RUN_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO(PASSWORD + "\n"))
    assert cli.main(["admin", "create", "--login", LOGIN, "--name", "Joël"]) == 0
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=migrated.app_url)
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        response = client.post("/api/auth/login", json={"login": LOGIN, "password": PASSWORD})
        headers = {CSRF_HEADER: response.json()["csrf_token"]}
        workspace = client.get("/api/workspaces").json()[0]["id"]
        yield client, headers, f"/api/workspaces/{workspace}"


def queued_jobs(database: TestDatabase) -> list[str]:
    with db.create_engine(database.admin_url).connect() as connection:
        return list(
            connection.execute(
                sa.text("SELECT task_name FROM procrastinate_jobs ORDER BY id")
            ).scalars()
        )


@pytest.mark.parametrize(
    "url", ["ftp://example.org/feed", "http://127.0.0.1/feed", "http://10.0.0.1/"]
)
def test_a_source_that_cannot_be_fetched_is_refused_with_a_code(
    signed_in: tuple[TestClient, dict[str, str], str], url: str
) -> None:
    client, headers, prefix = signed_in
    response = client.post(f"{prefix}/sources", json={"url": url}, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"] in ("invalid_url", "fetch_address_not_allowed")
    assert client.get(f"{prefix}/sources").json() == []


def test_the_interval_is_bounded(signed_in: tuple[TestClient, dict[str, str], str]) -> None:
    client, headers, prefix = signed_in
    response = client.post(
        f"{prefix}/sources",
        json={"url": "https://example.org/feed", "interval_minutes": 5},
        headers=headers,
    )
    assert response.status_code == 422


def test_a_pasted_text_is_kept_with_its_declaration(
    signed_in: tuple[TestClient, dict[str, str], str],
) -> None:
    client, headers, prefix = signed_in
    body = {
        "title": "Compte rendu",
        "text": "Mon propre texte.",
        "declared_origin": "Mes notes",
        "usage_right": "J'en suis l'auteur",
    }
    created = client.post(f"{prefix}/items/manual-text", json=body, headers=headers)
    assert created.status_code == 201, created.text
    item = created.json()
    assert (item["origin"], item["text_status"], item["declared_origin"]) == (
        "manual_text",
        "manual",
        "Mes notes",
    )
    listed = client.get(f"{prefix}/items").json()
    assert [i["id"] for i in listed] == [item["id"]]
    assert listed[0]["text"] is None  # the list leaves the texts out
    assert client.get(f"{prefix}/items/{item['id']}").json()["text"] == "Mon propre texte."
    missing = client.post(
        f"{prefix}/items/manual-text", json={**body, "usage_right": " "}, headers=headers
    )
    assert (missing.status_code, missing.json()["detail"]) == (422, "invalid_declaration")


def test_a_pointed_page_is_queued_for_reading(
    migrated: TestDatabase, signed_in: tuple[TestClient, dict[str, str], str]
) -> None:
    client, headers, prefix = signed_in
    created = client.post(
        f"{prefix}/items/manual-url", json={"url": "https://example.org/a"}, headers=headers
    )
    assert created.status_code == 201
    assert created.json()["text_status"] == "pending"
    assert queued_jobs(migrated) == ["collection.extract_item"]


def test_unknown_sources_answer_404(signed_in: tuple[TestClient, dict[str, str], str]) -> None:
    client, headers, prefix = signed_in
    unknown = "01890000-0000-7000-8000-000000000000"
    for method in ("GET", "PATCH", "DELETE"):
        response = client.request(method, f"{prefix}/sources/{unknown}", json={}, headers=headers)
        assert (response.status_code, response.json()["detail"]) == (404, "source_not_found")
    response = client.post(f"{prefix}/sources/{unknown}/collect", headers=headers)
    assert response.status_code == 404
