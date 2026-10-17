# SPDX-License-Identifier: AGPL-3.0-or-later
"""The models of a local engine (F05b): listing what Ollama has installed, and installing a
model, against a fake of its native API, then through the service and its rules."""

import json
import threading
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from otlet.ai.adapters.catalogue_file import PackagedCatalogue
from otlet.ai.adapters.ollama import OllamaHost, root
from otlet.ai.application.models import InstalledModel, Models, Pull
from otlet.ai.domain.model import AiError
from otlet.ai.domain.settings import InstancePolicy, Provider, SettingsError

CATALOGUE = PackagedCatalogue().load()
USER = uuid.uuid4()


class FakeOllama:
    """The two calls of the native API that Otlet makes."""

    def __init__(self) -> None:
        self.installed = [
            {"name": "qwen3:14b", "size": 9_300_000_000},
            {"name": "Llama3.1", "size": 4_900_000_000},
        ]
        self.pull_lines: list[dict[str, Any]] = [{"status": "success"}]
        self.pulled: list[str] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                payload = json.dumps({"models": fake.installed}).encode()
                self.send_response(200 if self.path == "/api/tags" else 404)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.pulled.append(body["model"])
                payload = "".join(json.dumps(line) + "\n" for line in fake.pull_lines).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.endpoint = f"http://127.0.0.1:{self.port}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def policy(self, *, install: bool = True) -> InstancePolicy:
        return InstancePolicy.checked([], ["127.0.0.0/8"], [self.port], CATALOGUE, install)


@pytest.fixture
def ollama() -> Iterator[FakeOllama]:
    fake = FakeOllama()
    yield fake
    fake.server.shutdown()


def test_the_root_of_the_engine_is_the_address_without_its_path() -> None:
    assert root("http://192.168.129.45:11434/v1") == "http://192.168.129.45:11434"


def test_the_installed_models_are_listed_in_alphabetical_order(ollama: FakeOllama) -> None:
    found = OllamaHost().installed(ollama.endpoint, ollama.policy())
    assert found == [
        InstalledModel("Llama3.1", 4_900_000_000),
        InstalledModel("qwen3:14b", 9_300_000_000),
    ]


def test_an_engine_off_the_allowed_networks_is_not_reached(ollama: FakeOllama) -> None:
    with pytest.raises(AiError) as caught:
        OllamaHost().installed(ollama.endpoint, InstancePolicy())  # nothing allowed
    assert (caught.value.kind, caught.value.detail) == ("unavailable", "address_not_allowed")
    stopped = InstancePolicy.checked([], ["127.0.0.0/8"], [1], CATALOGUE)
    with pytest.raises(AiError):
        OllamaHost().installed("http://127.0.0.1:1/v1", stopped)  # nobody there


def test_a_download_reports_its_progress_across_layers(ollama: FakeOllama) -> None:
    ollama.pull_lines = [
        {"status": "pulling manifest"},
        {"status": "pulling aaa", "digest": "aaa", "total": 1000, "completed": 400},
        {"status": "pulling aaa", "digest": "aaa", "total": 1000, "completed": 1000},
        {"status": "pulling bbb", "digest": "bbb", "total": 200, "completed": 50},
        {"status": "success"},
    ]
    seen: list[tuple[str, int, int]] = []
    OllamaHost().pull(ollama.endpoint, ollama.policy(), "qwen3:14b", lambda *a: seen.append(a))
    assert ollama.pulled == ["qwen3:14b"]
    # Throttled to one report a second, the last one is always sent: the layers added up.
    assert seen[-1] == ("success", 1050, 1200)


def test_a_refused_or_cut_download_is_an_error(ollama: FakeOllama) -> None:
    host, policy = OllamaHost(), ollama.policy()
    ollama.pull_lines = [{"error": "pull model manifest: file does not exist"}]
    with pytest.raises(AiError) as caught:
        host.pull(ollama.endpoint, policy, "nope", lambda *a: None)
    assert caught.value.kind == "refused" and "does not exist" in caught.value.detail
    ollama.pull_lines = [{"status": "pulling manifest"}]  # the stream stops without « success »
    with pytest.raises(AiError) as caught:
        host.pull(ollama.endpoint, policy, "qwen3:14b", lambda *a: None)
    assert caught.value.kind == "unavailable"


class Settings:
    def __init__(self, providers: list[Provider], policy: InstancePolicy) -> None:
        self.providers, self._policy = providers, policy

    def list_providers(self, user_id: uuid.UUID) -> list[Provider]:
        return self.providers if user_id == USER else []

    def policy(self) -> InstancePolicy:
        return self._policy


class Host:
    def __init__(self) -> None:
        self.error: AiError | None = None
        self.pulled: list[str] = []

    def installed(self, endpoint: str, policy: InstancePolicy) -> list[InstalledModel]:
        if self.error is not None:
            raise self.error
        return [InstalledModel("a", 1)]

    def pull(
        self, endpoint: str, policy: InstancePolicy, model: str, progress: Callable[..., None]
    ) -> None:
        self.pulled.append(model)
        progress("pulling x", 5, 10)
        if self.error is not None:
            raise self.error


class Pulls:
    def __init__(self) -> None:
        self.records: dict[uuid.UUID, Pull] = {}

    def create(
        self, user_id: uuid.UUID, pull_id: uuid.UUID, provider_id: uuid.UUID, model: str
    ) -> Pull:
        pull = Pull(pull_id, provider_id, model, "running", "", 0, 0, None, datetime.now(UTC), None)
        self.records[pull_id] = pull
        return pull

    def get(self, user_id: uuid.UUID, pull_id: uuid.UUID) -> Pull | None:
        return self.records.get(pull_id)

    def progress(
        self, user_id: uuid.UUID, pull_id: uuid.UUID, step: str, completed: int, total: int
    ) -> None:
        old = self.records[pull_id]
        self.records[pull_id] = Pull(
            old.id,
            old.provider_id,
            old.model,
            "running",
            step,
            completed,
            total,
            None,
            old.created_at,
            None,
        )

    def finish(self, user_id: uuid.UUID, pull_id: uuid.UUID, error: str | None) -> None:
        old = self.records[pull_id]
        self.records[pull_id] = Pull(
            old.id,
            old.provider_id,
            old.model,
            "done" if error is None else "failed",
            old.step,
            old.completed,
            old.total,
            error,
            old.created_at,
            datetime.now(UTC),
        )


def provider(kind: str) -> Provider:
    return Provider(
        uuid.uuid4(), USER, kind, kind, "http://192.168.129.45:11434/v1", None, datetime.now(UTC)
    )


def service(kind: str = "ollama", *, install: bool = True) -> tuple[Models, Provider, Host, Pulls]:
    mine = provider(kind)
    policy = InstancePolicy.checked([], ["192.168.129.0/24"], [11434], CATALOGUE, install)
    host, pulls = Host(), Pulls()
    models = Models(Settings([mine], policy), CATALOGUE, host, pulls, uuid.uuid4)
    return models, mine, host, pulls


def test_only_a_local_engine_of_the_user_lists_and_installs() -> None:
    models, mine, *_ = service("groq")
    for call in (
        lambda: models.installed(USER, mine.id),
        lambda: models.start_pull(USER, mine.id, "qwen3:14b"),
    ):
        with pytest.raises(SettingsError) as caught:
            call()
        assert caught.value.code == "not_a_local_engine"
    models, mine, *_ = service()
    with pytest.raises(SettingsError) as caught:
        models.installed(uuid.uuid4(), mine.id)  # another user
    assert caught.value.code == "unknown_provider"
    with pytest.raises(SettingsError) as caught:
        models.start_pull(USER, uuid.uuid4(), "qwen3:14b")
    assert caught.value.code == "unknown_provider"


def test_the_list_says_whether_the_administrator_allows_installing() -> None:
    for allowed in (True, False):
        models, mine, *_ = service(install=allowed)
        listed = models.installed(USER, mine.id)
        assert [m.name for m in listed.models] == ["a"] and listed.can_install is allowed


def test_an_unreachable_engine_is_a_setting_error() -> None:
    models, mine, host, _ = service()
    host.error = AiError("unavailable", "address_not_allowed")
    with pytest.raises(SettingsError) as caught:
        models.installed(USER, mine.id)
    assert caught.value.code == "engine_unreachable"


def test_installing_needs_a_model_name_and_the_administrator() -> None:
    models, mine, _, pulls = service(install=False)
    with pytest.raises(SettingsError) as caught:
        models.start_pull(USER, mine.id, "qwen3:14b")
    assert caught.value.code == "install_not_allowed"
    models, mine, _, pulls = service()
    for bad in ("", "  ", "rm -rf /", "a b", "../../x", "x" * 101, "-flag"):
        with pytest.raises(SettingsError) as caught:
            models.start_pull(USER, mine.id, bad)
        assert caught.value.code == "invalid_model_name", bad
    assert pulls.records == {}
    started = models.start_pull(USER, mine.id, "  hf.co/org/model:Q4_K_M ")
    assert started.model == "hf.co/org/model:Q4_K_M" and started.status == "running"


def test_the_job_records_the_progress_then_the_end() -> None:
    models, mine, host, pulls = service()
    started = models.start_pull(USER, mine.id, "qwen3:14b")
    models.run_pull(USER, started.id)
    done = pulls.records[started.id]
    assert (done.status, done.error, done.completed, done.total) == ("done", None, 5, 10)
    assert host.pulled == ["qwen3:14b"]
    host.error = AiError("refused", "file does not exist")
    again = models.start_pull(USER, mine.id, "nope")
    models.run_pull(USER, again.id)
    failed = pulls.records[again.id]
    assert failed.status == "failed" and failed.error == "refused: file does not exist"


def test_the_job_checks_the_permission_again() -> None:
    models, mine, host, pulls = service()
    started = models.start_pull(USER, mine.id, "qwen3:14b")
    models._settings = Settings([mine], InstancePolicy())  # withdrawn since
    models.run_pull(USER, started.id)
    assert pulls.records[started.id].error == "install_not_allowed" and host.pulled == []
