# SPDX-License-Identifier: AGPL-3.0-or-later
"""What the gateway needs from the outside world (ADR-0027 §1)."""

from typing import Protocol
from uuid import UUID

from otlet.ai.domain.model import Answer, Catalogue, Completion
from otlet.ai.domain.settings import InstancePolicy, Profile, Provider


class Adapter(Protocol):
    def complete(self, call: Completion) -> Answer:
        """One call to the provider, without any retry of its own: the gateway alone decides
        (ADR-0027 §4). Raises AiError with a kind the gateway acts on."""
        ...


class CatalogueSource(Protocol):
    def load(self) -> Catalogue: ...


class SettingsStore(Protocol):
    """The providers and profile of a user, and the policy of the instance."""

    def list_providers(self, user_id: UUID) -> list[Provider]: ...

    def add_provider(
        self,
        user_id: UUID,
        provider_id: UUID,
        *,
        name: str,
        kind: str,
        endpoint: str,
        sealed_key: bytes | None,
        key_hint: str | None,
    ) -> Provider:
        """Raises SettingsError("name_taken") when the user has a provider of this name."""
        ...

    def update_provider(
        self,
        user_id: UUID,
        provider_id: UUID,
        *,
        name: str,
        endpoint: str,
        sealed_key: bytes | None,
        key_hint: str | None,
        replace_key: bool,
    ) -> Provider | None: ...

    def delete_provider(self, user_id: UUID, provider_id: UUID) -> bool: ...

    def profile(self, user_id: UUID) -> Profile: ...

    def save_profile(self, user_id: UUID, profile: Profile) -> None: ...

    def policy(self) -> InstancePolicy: ...

    def save_policy(self, policy: InstancePolicy) -> None: ...


class Sealer(Protocol):
    def seal(self, plaintext: bytes, context: bytes) -> bytes:
        """Seals a secret with the public key of the instance (DR6)."""
        ...
