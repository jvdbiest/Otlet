# SPDX-License-Identifier: AGPL-3.0-or-later
"""Who chooses what (ADR-0027, validation of Joël): the administrator of the instance allows
or blocks; each user chooses, among what is allowed, their providers and the ordered profile
of models the gateway tries.

- The instance policy lists the paid providers the administrator allowed, and the internal
  networks and ports a local engine may be reached at (Ollama on the network); everything else
  internal stays out of reach (SSRF).
- A user's provider is a kind of the catalogue, an address and, if the kind needs one, a key.
  The key is sealed by the API with the public key of the instance: only the worker can open
  it (DR6). The API keeps its last four characters to show which key is set.
- A user's profile is an ordered list of (provider, model): the gateway tries them in order.
"""

import ipaddress
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from otlet.ai.domain.model import Catalogue, ModelEntry, Status

NAME_MAX_LENGTH = 80
ENDPOINT_MAX_LENGTH = 300
KEY_MAX_LENGTH = 500
PROFILE_MAX = 8


class SettingsError(Exception):
    """A rule of the AI settings was not met; `code` is stable and translated by the interface."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class InstancePolicy:
    allowed_paid: frozenset[str] = frozenset()
    local_networks: tuple[str, ...] = ()  # CIDR, e.g. 192.168.1.0/24
    local_ports: tuple[int, ...] = ()
    # Users may have the local engine download models onto its machine (Ollama: pull).
    allow_model_install: bool = False

    @classmethod
    def checked(
        cls,
        allowed_paid: Iterable[str],
        networks: Iterable[str],
        ports: Iterable[int],
        catalogue: Catalogue,
        allow_model_install: bool = False,
    ) -> "InstancePolicy":
        paid = {e.provider for e in catalogue.entries if e.paid}
        allowed = frozenset(p.strip() for p in allowed_paid)
        if not allowed <= paid:
            raise SettingsError(
                "unknown_provider", f"not a paid provider: {sorted(allowed - paid)}"
            )
        cleaned: list[str] = []
        for network in networks:
            try:
                parsed = ipaddress.ip_network(network.strip(), strict=False)
            except ValueError as error:
                raise SettingsError("invalid_network", network) from error
            if parsed.is_global:
                raise SettingsError("invalid_network", f"{network} is public: no need to allow it")
            cleaned.append(str(parsed))
        checked_ports = tuple(sorted(set(ports)))
        if any(not 1 <= port <= 65535 for port in checked_ports):
            raise SettingsError("invalid_port", "a port is between 1 and 65535")
        return cls(allowed, tuple(dict.fromkeys(cleaned)), checked_ports, allow_model_install)

    def refuses(self, endpoint: str) -> bool:
        """An address written as an internal IP (or localhost) outside the networks and ports
        the administrator allowed: refused when the user saves it, so that they know at once.
        A host name is only resolved, and checked, at each call (SSRF)."""
        parts = urlsplit(endpoint)
        host = parts.hostname or ""
        if host == "localhost":
            host = "127.0.0.1"
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        if address.is_global:
            return False
        port = parts.port or (443 if parts.scheme == "https" else 80)
        allowed = any(address in ipaddress.ip_network(n) for n in self.local_networks)
        return not (allowed and port in self.local_ports)

    def status(self, entry: ModelEntry) -> Status:
        """The status a user sees: a paid model the administrator allowed is « non testé »
        until its 50 briefs are measured (ADR-0027 §7)."""
        if entry.status is Status.BLOCKED and entry.paid and entry.provider in self.allowed_paid:
            return Status.UNTESTED
        return entry.status


@dataclass(frozen=True, slots=True)
class Provider:
    id: UUID
    user_id: UUID
    name: str
    kind: str
    endpoint: str
    key_hint: str | None  # the last characters of the key, or None without a key
    created_at: datetime
    # The context window its models run with, in tokens; None: automatic, the window of each
    # model from the catalogue (a local engine: 4,096, Ollama's default). A local engine's
    # window depends on its machine (OLLAMA_CONTEXT_LENGTH): the user says it here.
    context_window: int | None = None


@dataclass(frozen=True, slots=True)
class ProfileEntry:
    provider_id: UUID
    model: str


@dataclass(frozen=True, slots=True)
class Profile:
    entries: tuple[ProfileEntry, ...] = field(default_factory=tuple)


def check_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not 1 <= len(cleaned) <= NAME_MAX_LENGTH:
        raise SettingsError("invalid_name", f"a name has 1 to {NAME_MAX_LENGTH} characters")
    return cleaned


def api_endpoint(endpoint: str, local: bool) -> str:
    """The address of the OpenAI-compatible API. A local engine (Ollama) serves it under /v1:
    an address given as the bare server (http://host:11434) gets it, as users often write it."""
    parts = urlsplit(endpoint)
    if local and parts.path in ("", "/"):
        return endpoint.rstrip("/") + "/v1"
    return endpoint


CONTEXT_WINDOW_RANGE = (2_048, 2_000_000)
LOCAL_DEFAULT_WINDOW = 4_096


def check_context_window(window: int | None) -> int | None:
    if window is not None and not CONTEXT_WINDOW_RANGE[0] <= window <= CONTEXT_WINDOW_RANGE[1]:
        raise SettingsError(
            "invalid_context_window",
            f"a context window is between {CONTEXT_WINDOW_RANGE[0]} and {CONTEXT_WINDOW_RANGE[1]}",
        )
    return window


def effective_window(provider: Provider, model_context: int, local: bool) -> int:
    """The window a call to this provider's model runs with: the user's setting, else the
    model's from the catalogue, else the default of a local engine."""
    if provider.context_window is not None:
        return provider.context_window
    if local or model_context <= 0:
        return LOCAL_DEFAULT_WINDOW
    return model_context


def check_endpoint(endpoint: str) -> str:
    """HTTP or HTTPS, a host, no credentials. Whether the address may be reached is decided at
    each call, after resolution (SSRF)."""
    cleaned = endpoint.strip().rstrip("/")
    parts = urlsplit(cleaned)
    if (
        len(cleaned) > ENDPOINT_MAX_LENGTH
        or parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise SettingsError("invalid_endpoint", "an address starts with http:// or https://")
    return cleaned


def check_key(key: str | None, required: bool) -> str | None:
    cleaned = None if key is None else key.strip()
    if cleaned == "":
        cleaned = None
    if cleaned is not None and len(cleaned) > KEY_MAX_LENGTH:
        raise SettingsError("invalid_key", f"a key has at most {KEY_MAX_LENGTH} characters")
    if required and cleaned is None:
        raise SettingsError("key_required", "this provider needs an API key")
    return cleaned


def key_hint(key: str) -> str:
    return key[-4:] if len(key) >= 12 else "…"


def check_profile(
    entries: Sequence[ProfileEntry],
    providers: Sequence[Provider],
    catalogue: Catalogue,
    policy: InstancePolicy,
) -> Profile:
    """Every entry names a provider of the user and a model that provider may run and the
    instance allows."""
    if len(entries) > PROFILE_MAX:
        raise SettingsError("profile_too_long", f"at most {PROFILE_MAX} models")
    by_id = {provider.id: provider for provider in providers}
    seen: set[tuple[UUID, str]] = set()
    for entry in entries:
        provider = by_id.get(entry.provider_id)
        if provider is None:
            raise SettingsError("unknown_provider", "not a provider of this user")
        model = catalogue.model(provider.kind, entry.model.strip())
        if model is None:
            raise SettingsError("unknown_model", f"{provider.kind} does not offer {entry.model}")
        if policy.status(model) is Status.BLOCKED:
            raise SettingsError("model_blocked", f"{provider.kind}/{entry.model} is blocked")
        key = (entry.provider_id, model.model)
        if key in seen:
            raise SettingsError("duplicate_model", "a model appears twice in the profile")
        seen.add(key)
    return Profile(tuple(ProfileEntry(e.provider_id, e.model.strip()) for e in entries))
