# SPDX-License-Identifier: AGPL-3.0-or-later
"""What the gateway needs from the outside world (ADR-0027 §1)."""

from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from otlet.ai.domain.budget import BudgetState, Reservation
from otlet.ai.domain.model import Answer, Catalogue, Completion
from otlet.ai.domain.settings import InstancePolicy, Profile, Provider


class Adapter(Protocol):
    def complete(self, call: Completion) -> Answer:
        """One call to the provider, without any retry of its own: the gateway alone decides
        (ADR-0027 §4). Raises AiError with a kind the gateway acts on."""
        ...

    def abort(self) -> None:
        """Called from another thread: cuts the call under way, which then raises."""
        ...


class CatalogueSource(Protocol):
    def load(self) -> Catalogue: ...


class SettingsStore(Protocol):
    """The providers and profile of a user, and the policy of the instance."""

    def set_context_window(
        self, user_id: UUID, provider_id: UUID, window: int | None
    ) -> Provider | None: ...

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


class BudgetStore(Protocol):
    def limit(self, user_id: UUID) -> Decimal: ...

    def set_limit(self, user_id: UUID, month: date, limit: Decimal) -> None: ...

    def state(self, user_id: UUID, month: date) -> BudgetState: ...

    def reserve(self, user_id: UUID, month: date, amount: Decimal) -> Reservation | None:
        """None when the reservation would go beyond the limit minus the guard band."""
        ...

    def settle(self, reservation: Reservation, cost: Decimal) -> None: ...
