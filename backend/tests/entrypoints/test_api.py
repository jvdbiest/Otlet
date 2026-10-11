# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from otlet import __version__
from otlet.entrypoints.api.app import create_app
from otlet.platform.config import Settings

INDEX = "<!doctype html><title>Otlet</title>"


@pytest.fixture
def ui_dir(tmp_path: Path) -> Path:
    ui = tmp_path / "ui"
    (ui / "assets").mkdir(parents=True)
    (ui / "index.html").write_text(INDEX, encoding="utf-8")
    (ui / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return ui


@pytest.fixture
def client(ui_dir: Path, tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(ui_dir=ui_dir, run_dir=tmp_path / "run")))


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_serves_the_interface(client: TestClient) -> None:
    assert client.get("/").text == INDEX
    assert client.get("/assets/app.js").text == "console.log(1)"


def test_client_routes_fall_back_to_the_interface(client: TestClient) -> None:
    response = client.get("/library/42")
    assert response.status_code == 200
    assert response.text == INDEX


def test_missing_files_stay_missing(client: TestClient) -> None:
    assert client.get("/assets/missing.js").status_code == 404


def test_runs_without_interface(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(ui_dir=None, run_dir=tmp_path)))
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 404


def test_health_reports_an_unreachable_database(tmp_path: Path) -> None:
    # Port 9 (discard) is never served in a test environment: the connection is refused.
    settings = Settings(
        ui_dir=None,
        run_dir=tmp_path,
        database_url="postgresql+psycopg://otlet:secret@127.0.0.1:9/otlet",
    )
    response = TestClient(create_app(settings)).get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
