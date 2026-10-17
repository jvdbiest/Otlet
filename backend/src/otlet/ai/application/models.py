# SPDX-License-Identifier: AGPL-3.0-or-later
"""The models of a local engine (F05b): which ones are installed, and installing one.

Only a provider whose kind runs models the catalogue does not list (Ollama) has this. Listing is
a read of the engine. Installing makes the engine download a model onto its own machine: the
administrator of the instance must have allowed it, since the engine may be shared. The
download is a job of the worker, which writes its progress for the interface.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from otlet.ai.domain.model import AiError, Catalogue
from otlet.ai.domain.settings import InstancePolicy, Provider, SettingsError

PULL_MODEL = "ai.pull_model"
# A name as Ollama writes them: qwen3:14b, llama3.1, hf.co/org/model:Q4_K_M.
MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")


@dataclass(frozen=True, slots=True)
class InstalledModel:
    name: str
    size: int  # bytes


@dataclass(frozen=True, slots=True)
class Installed:
    models: tuple[InstalledModel, ...]
    can_install: bool  # the administrator allows installing


@dataclass(frozen=True, slots=True)
class Pull:
    id: UUID
    provider_id: UUID
    model: str
    status: str  # running, done, failed
    step: str  # what the engine says it is doing: « pulling manifest »…
    completed: int  # bytes
    total: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class ModelHost(Protocol):
    """A local engine, spoken to in its own protocol."""

    def installed(self, endpoint: str, policy: InstancePolicy) -> list[InstalledModel]:
        """Raises AiError("unavailable") when the engine does not answer."""
        ...

    def pull(
        self,
        endpoint: str,
        policy: InstancePolicy,
        model: str,
        progress: Callable[[str, int, int], None],
    ) -> None:
        """Downloads the model, calling `progress(step, completed, total)` as it goes. Raises
        AiError("unavailable") when the engine does not answer, AiError("refused") when it
        refuses the model."""
        ...


class PullStore(Protocol):
    def create(self, user_id: UUID, pull_id: UUID, provider_id: UUID, model: str) -> Pull:
        """Creates the installation and enqueues its job in the same transaction."""
        ...

    def get(self, user_id: UUID, pull_id: UUID) -> Pull | None: ...

    def progress(
        self, user_id: UUID, pull_id: UUID, step: str, completed: int, total: int
    ) -> None: ...

    def finish(self, user_id: UUID, pull_id: UUID, error: str | None) -> None: ...


class ProviderSource(Protocol):
    def list_providers(self, user_id: UUID) -> list[Provider]: ...

    def policy(self) -> InstancePolicy: ...


class Models:
    def __init__(
        self,
        settings: ProviderSource,
        catalogue: Catalogue,
        host: ModelHost,
        pulls: PullStore,
        new_id: Callable[[], UUID],
    ) -> None:
        self._settings = settings
        self._catalogue = catalogue
        self._host = host
        self._pulls = pulls
        self._new_id = new_id

    def installed(self, user_id: UUID, provider_id: UUID) -> Installed:
        provider = self._local_provider(user_id, provider_id)
        policy = self._settings.policy()
        try:
            models = self._host.installed(provider.endpoint, policy)
        except AiError as error:
            raise SettingsError("engine_unreachable", error.detail) from error
        return Installed(tuple(models), policy.allow_model_install)

    def start_pull(self, user_id: UUID, provider_id: UUID, model: str) -> Pull:
        self._local_provider(user_id, provider_id)
        name = model.strip()
        if not MODEL_NAME.fullmatch(name):
            raise SettingsError("invalid_model_name", "not a model name")
        if not self._settings.policy().allow_model_install:
            raise SettingsError(
                "install_not_allowed", "the administrator did not allow installing models"
            )
        return self._pulls.create(user_id, self._new_id(), provider_id, name)

    def get_pull(self, user_id: UUID, pull_id: UUID) -> Pull | None:
        return self._pulls.get(user_id, pull_id)

    def run_pull(self, user_id: UUID, pull_id: UUID) -> None:
        """The job: follows the download of the engine and records how far it went."""
        pull = self._pulls.get(user_id, pull_id)
        if pull is None:
            return
        policy = self._settings.policy()
        provider = next(
            (p for p in self._settings.list_providers(user_id) if p.id == pull.provider_id), None
        )
        if provider is None or not policy.allow_model_install:
            self._pulls.finish(user_id, pull_id, "install_not_allowed")
            return

        def progress(step: str, completed: int, total: int) -> None:
            self._pulls.progress(user_id, pull_id, step, completed, total)

        try:
            self._host.pull(provider.endpoint, policy, pull.model, progress)
        except AiError as error:
            self._pulls.finish(user_id, pull_id, f"{error.kind}: {error.detail}"[:300])
        else:
            self._pulls.finish(user_id, pull_id, None)

    def _local_provider(self, user_id: UUID, provider_id: UUID) -> Provider:
        provider = next(
            (p for p in self._settings.list_providers(user_id) if p.id == provider_id), None
        )
        if provider is None:
            raise SettingsError("unknown_provider", "not a provider of the user")
        kind = self._catalogue.kind(provider.kind)
        if kind is None or not kind.custom_models:
            raise SettingsError("not_a_local_engine", "only a local engine lists its models")
        return provider
