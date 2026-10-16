# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sign-in through the API on a real PostgreSQL (F02): sessions, CSRF, throttle,
re-authentication, and the command that creates the administrator account."""

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from integration_support import TestDatabase, requires_database
from otlet.entrypoints import cli
from otlet.entrypoints.api.app import create_app
from otlet.entrypoints.api.auth import COOKIE, CSRF_HEADER
from otlet.identity.domain import model
from otlet.platform import database as db
from otlet.platform.config import Settings

pytestmark = requires_database

LOGIN = "joel@example.org"
PASSWORD = "une phrase de passe assez longue"  # noqa: S105 (test account)


def admin_sql(database: TestDatabase, statement: str) -> None:
    with db.create_engine(database.admin_url).begin() as connection:
        connection.execute(sa.text(statement))


def count(database: TestDatabase, table: str) -> int:
    with db.create_engine(database.admin_url).connect() as connection:
        return int(connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


@pytest.fixture
def admin(migrated: TestDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    """The administrator account, created by `otlet admin create` as an operator would."""
    monkeypatch.setenv("OTLET_DATABASE_URL", migrated.app_url)
    monkeypatch.setenv("OTLET_RUN_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO(PASSWORD + "\n"))
    assert cli.main(["admin", "create", "--login", " Joel@Example.org", "--name", "Joël"]) == 0
    return LOGIN


@pytest.fixture
def client(migrated: TestDatabase, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=migrated.app_url)
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        yield client


def sign_in(client: TestClient, password: str = PASSWORD) -> str:
    response = client.post("/api/auth/login", json={"login": LOGIN, "password": password})
    assert response.status_code == 200, response.text
    return str(response.json()["csrf_token"])


def test_sign_in_opens_a_session(admin: str, client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"login": "JOEL@example.org", "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["display_name"] == "Joël"
    assert body["user"]["is_instance_admin"] is True
    cookie = response.headers["set-cookie"]
    for attribute in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"):
        assert attribute in cookie
    assert client.get("/api/auth/session").json() == body


def test_only_the_token_digest_is_stored(
    admin: str, client: TestClient, migrated: TestDatabase
) -> None:
    sign_in(client)
    token = client.cookies[COOKIE]
    with db.create_engine(migrated.admin_url).connect() as connection:
        stored = connection.execute(sa.text("SELECT token_hash FROM user_sessions")).scalar_one()
    assert bytes(stored) == model.token_hash(token)


def test_wrong_password_and_unknown_login_look_the_same(admin: str, client: TestClient) -> None:
    wrong = client.post("/api/auth/login", json={"login": LOGIN, "password": "pas le bon mot"})
    unknown = client.post("/api/auth/login", json={"login": "x@example.org", "password": PASSWORD})
    assert (wrong.status_code, wrong.json()) == (unknown.status_code, unknown.json())
    assert wrong.status_code == 401
    assert client.get("/api/auth/session").status_code == 401


def test_repeated_failures_are_throttled(admin: str, client: TestClient) -> None:
    for _ in range(model.THROTTLE_MAX_FAILURES_PER_LOGIN):
        assert (
            client.post("/api/auth/login", json={"login": LOGIN, "password": "faux"}).status_code
            == 401
        )
    # Even the right password is refused until the window ends.
    blocked = client.post("/api/auth/login", json={"login": LOGIN, "password": PASSWORD})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) == int(model.THROTTLE_WINDOW.total_seconds())


def test_a_success_clears_the_login_counter(admin: str, client: TestClient) -> None:
    for _ in range(model.THROTTLE_MAX_FAILURES_PER_LOGIN - 1):
        client.post("/api/auth/login", json={"login": LOGIN, "password": "faux"})
    sign_in(client)
    assert (
        client.post("/api/auth/login", json={"login": LOGIN, "password": "faux"}).status_code == 401
    )
    sign_in(client)


def test_state_changes_require_the_csrf_token(admin: str, client: TestClient) -> None:
    csrf = sign_in(client)
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post("/api/auth/logout", headers={CSRF_HEADER: "x" * 64}).status_code == 403
    assert client.post("/api/auth/logout", headers={CSRF_HEADER: csrf}).status_code == 204
    assert client.get("/api/auth/session").status_code == 401


def test_cross_site_requests_are_refused(admin: str, client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"login": LOGIN, "password": PASSWORD},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403


def test_sign_out_deletes_the_session(
    admin: str, client: TestClient, migrated: TestDatabase
) -> None:
    csrf = sign_in(client)
    token = client.cookies[COOKIE]
    client.post("/api/auth/logout", headers={CSRF_HEADER: csrf})
    assert count(migrated, "user_sessions") == 0
    client.cookies.set(COOKIE, token)  # a copied cookie is worthless once signed out
    assert client.get("/api/auth/session").status_code == 401


def test_an_idle_session_expires_and_is_deleted(
    admin: str, client: TestClient, migrated: TestDatabase
) -> None:
    sign_in(client)
    admin_sql(migrated, "UPDATE user_sessions SET last_seen_at = now() - interval '13 hours'")
    assert client.get("/api/auth/session").status_code == 401
    assert count(migrated, "user_sessions") == 0


def test_a_disabled_account_loses_its_session(
    admin: str, client: TestClient, migrated: TestDatabase
) -> None:
    sign_in(client)
    admin_sql(migrated, "UPDATE users SET disabled_at = now()")
    assert client.get("/api/auth/session").status_code == 401
    response = client.post("/api/auth/login", json={"login": LOGIN, "password": PASSWORD})
    assert response.status_code == 401


def test_changing_the_password_requires_a_recent_reauthentication(
    admin: str, client: TestClient, migrated: TestDatabase
) -> None:
    csrf = sign_in(client)
    admin_sql(migrated, "UPDATE user_sessions SET reauthenticated_at = now() - interval '1 hour'")
    new = {"new_password": "une autre phrase de passe"}
    headers = {CSRF_HEADER: csrf}

    assert client.post("/api/auth/password", json=new, headers=headers).status_code == 403
    wrong = client.post("/api/auth/reauthenticate", json={"password": "faux"}, headers=headers)
    assert wrong.status_code == 401
    right = client.post("/api/auth/reauthenticate", json={"password": PASSWORD}, headers=headers)
    assert right.status_code == 204
    assert client.post("/api/auth/password", json=new, headers=headers).status_code == 204

    assert (
        client.post("/api/auth/login", json={"login": LOGIN, "password": PASSWORD}).status_code
        == 401
    )
    sign_in(client, new["new_password"])


def test_a_new_password_ends_the_other_sessions(
    admin: str, client: TestClient, migrated: TestDatabase, tmp_path: Path
) -> None:
    settings = Settings(ui_dir=None, run_dir=tmp_path, database_url=migrated.app_url)
    with TestClient(create_app(settings), base_url="https://testserver") as other:
        sign_in(other)
        csrf = sign_in(client)
        response = client.post(
            "/api/auth/password",
            json={"new_password": "une autre phrase de passe"},
            headers={CSRF_HEADER: csrf},
        )
        assert response.status_code == 204
        assert other.get("/api/auth/session").status_code == 401
        assert client.get("/api/auth/session").status_code == 200


def test_weak_passwords_are_refused(admin: str, client: TestClient) -> None:
    csrf = sign_in(client)
    response = client.post(
        "/api/auth/password", json={"new_password": "court"}, headers={CSRF_HEADER: csrf}
    )
    assert response.status_code == 422


def test_admin_create_refuses_a_taken_login(admin: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(PASSWORD + "\n"))
    assert cli.main(["admin", "create", "--login", LOGIN, "--name", "Autre"]) == 2


def test_admin_create_refuses_a_weak_password(
    migrated: TestDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OTLET_DATABASE_URL", migrated.app_url)
    monkeypatch.setattr("sys.stdin", io.StringIO("court\n"))
    assert cli.main(["admin", "create", "--login", LOGIN, "--name", "Joël"]) == 2
    assert count(migrated, "users") == 0
