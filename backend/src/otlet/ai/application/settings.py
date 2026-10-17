# SPDX-License-Identifier: AGPL-3.0-or-later
"""The AI settings of a user, and the policy of the instance (F05, ADR-0027).

The user chooses their providers and models; the administrator allows or blocks. Keys are
sealed here, in the API, and never come back out of it: only the worker opens them (DR6).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from otlet.ai.application.ports import Sealer, SettingsStore
from otlet.ai.domain.model import Catalogue, ModelEntry, Status
from otlet.ai.domain.settings import (
    InstancePolicy,
    Profile,
    ProfileEntry,
    Provider,
    SettingsError,
    check_endpoint,
    check_key,
    check_name,
    check_profile,
    key_hint,
)

KEY_CONTEXT = "ai-provider:"


def key_context(provider_id: UUID) -> bytes:
    """Associated data binding a sealed key to its provider: it cannot be moved to another."""
    return f"{KEY_CONTEXT}{provider_id}".encode()


@dataclass(frozen=True, slots=True)
class OfferedModel:
    """A model as a user sees it: its catalogue entry and the status the instance gives it."""

    entry: ModelEntry
    status: Status


class AiSettings:
    def __init__(self, store: SettingsStore, catalogue: Catalogue, sealer: Sealer) -> None:
        self._store = store
        self._catalogue = catalogue
        self._sealer = sealer

    # What the instance offers ----------------------------------------------------------------

    @property
    def catalogue(self) -> Catalogue:
        return self._catalogue

    def offered(self) -> list[OfferedModel]:
        policy = self._store.policy()
        return [OfferedModel(entry, policy.status(entry)) for entry in self._catalogue.entries]

    def policy(self) -> InstancePolicy:
        return self._store.policy()

    def set_policy(
        self,
        *,
        is_admin: bool,
        allowed_paid: Sequence[str],
        networks: Sequence[str],
        ports: Sequence[int],
    ) -> InstancePolicy:
        if not is_admin:
            raise SettingsError("admin_only", "only the administrator of the instance decides")
        policy = InstancePolicy.checked(allowed_paid, networks, ports, self._catalogue)
        self._store.save_policy(policy)
        return policy

    # The providers of a user -------------------------------------------------------------------

    def providers(self, user_id: UUID) -> list[Provider]:
        return self._store.list_providers(user_id)

    def add_provider(
        self, user_id: UUID, *, name: str, kind: str, endpoint: str | None, api_key: str | None
    ) -> Provider:
        found = self._catalogue.kind(kind)
        if found is None:
            raise SettingsError("unknown_kind", f"unknown provider kind {kind}")
        key = check_key(api_key, required=found.api_key)
        address = self._reachable(endpoint or found.endpoint)
        provider_id = uuid.uuid4()
        return self._store.add_provider(
            user_id,
            provider_id,
            name=check_name(name),
            kind=found.name,
            endpoint=address,
            sealed_key=None
            if key is None
            else self._sealer.seal(key.encode(), key_context(provider_id)),
            key_hint=None if key is None else key_hint(key),
        )

    def update_provider(
        self,
        user_id: UUID,
        provider_id: UUID,
        *,
        name: str,
        endpoint: str,
        api_key: str | None,
        replace_key: bool,
    ) -> Provider | None:
        """`replace_key` False keeps the sealed key as it is, whatever `api_key` holds: the key
        is never sent back to the interface, so an untouched form keeps it."""
        current = next(
            (p for p in self._store.list_providers(user_id) if p.id == provider_id), None
        )
        if current is None:
            return None
        kind = self._catalogue.kind(current.kind)
        key = check_key(api_key, required=replace_key and kind is not None and kind.api_key)
        address = self._reachable(endpoint)
        return self._store.update_provider(
            user_id,
            provider_id,
            name=check_name(name),
            endpoint=address,
            sealed_key=None
            if key is None
            else self._sealer.seal(key.encode(), key_context(provider_id)),
            key_hint=None if key is None else key_hint(key),
            replace_key=replace_key,
        )

    def _reachable(self, endpoint: str) -> str:
        cleaned = check_endpoint(endpoint)
        if self._store.policy().refuses(cleaned):
            raise SettingsError(
                "address_not_allowed",
                "an internal address must be allowed by the administrator of the instance",
            )
        return cleaned

    def delete_provider(self, user_id: UUID, provider_id: UUID) -> bool:
        return self._store.delete_provider(user_id, provider_id)

    # The profile of a user ---------------------------------------------------------------------

    def profile(self, user_id: UUID) -> Profile:
        return self._store.profile(user_id)

    def set_profile(self, user_id: UUID, entries: Sequence[ProfileEntry]) -> Profile:
        profile = check_profile(
            entries, self._store.list_providers(user_id), self._catalogue, self._store.policy()
        )
        self._store.save_profile(user_id, profile)
        return profile
