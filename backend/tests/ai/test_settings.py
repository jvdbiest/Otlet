# SPDX-License-Identifier: AGPL-3.0-or-later
"""Providers, profiles and the instance policy (F05, ADR-0027: the user chooses, the
administrator allows or blocks)."""

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from integration_support import TestDatabase, requires_database
from otlet.ai.adapters.catalogue_file import PackagedCatalogue
from otlet.ai.adapters.postgres import PostgresAiSettings
from otlet.ai.adapters.sealing import PublicKeySealer
from otlet.ai.application.settings import AiSettings, key_context
from otlet.ai.domain.model import Status
from otlet.ai.domain.settings import InstancePolicy, ProfileEntry, SettingsError, api_endpoint
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db
from otlet.platform.secrets.opening import open_sealed

CATALOGUE = PackagedCatalogue().load()


def test_a_paid_provider_becomes_untested_once_the_administrator_allows_it() -> None:
    groq = next(e for e in CATALOGUE.entries if e.provider == "groq")
    assert InstancePolicy().status(groq) is Status.BLOCKED
    policy = InstancePolicy.checked(["groq"], ["172.20.0.0/16"], [11434], CATALOGUE)
    assert policy.status(groq) is Status.UNTESTED
    with pytest.raises(SettingsError) as caught:
        InstancePolicy.checked(["ollama"], [], [], CATALOGUE)  # not a paid provider
    assert caught.value.code == "unknown_provider"
    with pytest.raises(SettingsError) as caught:
        InstancePolicy.checked([], ["8.8.8.0/24"], [], CATALOGUE)  # public: nothing to allow
    assert caught.value.code == "invalid_network"


def test_an_internal_address_needs_the_network_and_the_port_allowed() -> None:
    policy = InstancePolicy.checked([], ["192.168.129.249/32"], [11434], CATALOGUE)
    assert not policy.refuses("http://192.168.129.249:11434/v1")
    assert policy.refuses("http://192.168.129.249:8080/v1")  # port not allowed
    assert policy.refuses("http://192.168.129.250:11434/v1")  # network not allowed
    assert policy.refuses("http://localhost:11434/v1")
    assert InstancePolicy().refuses("http://10.0.0.5:11434/v1")
    # Public addresses, and host names (resolved and checked at each call), pass here.
    assert not InstancePolicy().refuses("https://api.groq.com/openai/v1")
    assert not InstancePolicy().refuses("https://8.8.8.8/v1")


def test_a_local_engine_given_as_a_bare_server_gets_its_api_path() -> None:
    assert (
        api_endpoint("http://192.168.129.45:11434", local=True) == "http://192.168.129.45:11434/v1"
    )
    assert (
        api_endpoint("http://192.168.129.45:11434/", local=True) == "http://192.168.129.45:11434/v1"
    )
    assert api_endpoint("http://h:11434/v1", local=True) == "http://h:11434/v1"
    assert api_endpoint("https://api.anthropic.com", local=False) == "https://api.anthropic.com"


def test_a_local_engine_may_run_a_model_the_catalogue_does_not_list() -> None:
    custom = CATALOGUE.model("ollama", "mistral:7b")
    assert custom is not None and custom.status is Status.UNTESTED and custom.price_in == 0
    assert CATALOGUE.model("groq", "some-unlisted-model") is None


@pytest.fixture
def keys(tmp_path: Path) -> tuple[X25519PrivateKey, Path]:
    private = X25519PrivateKey.generate()
    public_file = tmp_path / "public.pem"
    public_file.write_bytes(
        private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return private, public_file


def user(engine: sa.Engine, login: str, *, admin: bool = False) -> uuid.UUID:
    created: uuid.UUID = Authentication(PostgresIdentityStore(engine), Argon2Hasher()).create_user(
        login, login, "une phrase de passe assez longue", is_instance_admin=admin
    )
    return created


@requires_database
def test_providers_keys_and_profiles_belong_to_their_user(
    migrated: TestDatabase, keys: tuple[X25519PrivateKey, Path]
) -> None:
    private, public_file = keys
    engine = db.create_engine(migrated.app_url)
    store = PostgresAiSettings(engine)
    settings = AiSettings(store, CATALOGUE, PublicKeySealer(public_file))
    alice, bob = user(engine, "alice@example.org"), user(engine, "bob@example.org")

    local = settings.add_provider(
        alice, name="Ollama du NAS", kind="ollama", endpoint="http://nas:11434/v1", api_key=None
    )
    assert (local.endpoint, local.key_hint) == ("http://nas:11434/v1", None)
    with pytest.raises(SettingsError) as caught:
        settings.add_provider(alice, name="Groq", kind="groq", endpoint=None, api_key="")
    assert caught.value.code == "key_required"
    groq = settings.add_provider(
        alice, name="Groq", kind="groq", endpoint=None, api_key="gsk-secret-123456"
    )
    assert (groq.endpoint, groq.key_hint) == ("https://api.groq.com/openai/v1", "3456")
    with pytest.raises(SettingsError) as caught:
        settings.add_provider(
            alice, name="Groq", kind="groq", endpoint=None, api_key="other-key-123456"
        )
    assert caught.value.code == "name_taken"

    # The key is sealed: only the private key of the worker opens it, and only for this provider.
    with engine.connect() as connection:
        connection.execute(
            sa.text("SELECT set_config('app.user_id', :u, false)"), {"u": str(alice)}
        )
        sealed = connection.execute(
            sa.text("SELECT api_key_sealed FROM ai_providers WHERE id = :id"), {"id": groq.id}
        ).scalar_one()
    assert b"gsk-secret" not in sealed
    assert open_sealed(private, sealed, key_context(groq.id)) == b"gsk-secret-123456"

    # An untouched form keeps the key; replacing it reseals.
    renamed = settings.update_provider(
        alice, groq.id, name="Groq perso", endpoint=groq.endpoint, api_key=None, replace_key=False
    )
    assert renamed is not None and (renamed.name, renamed.key_hint) == ("Groq perso", "3456")

    # The profile: a blocked paid model is refused until the administrator allows the provider.
    with pytest.raises(SettingsError) as caught:
        settings.set_profile(alice, [ProfileEntry(groq.id, "llama-3.3-70b-versatile")])
    assert caught.value.code == "model_blocked"
    with pytest.raises(SettingsError) as caught:
        settings.set_policy(is_admin=False, allowed_paid=["groq"], networks=[], ports=[])
    assert caught.value.code == "admin_only"
    settings.set_policy(
        is_admin=True, allowed_paid=["groq"], networks=["192.168.1.0/24"], ports=[11434]
    )
    profile = settings.set_profile(
        alice,
        [
            ProfileEntry(local.id, "qwen2.5:1.5b-instruct"),
            ProfileEntry(groq.id, "llama-3.3-70b-versatile"),
        ],
    )
    assert [e.model for e in settings.profile(alice).entries] == [e.model for e in profile.entries]
    with pytest.raises(SettingsError) as caught:
        settings.set_profile(alice, [ProfileEntry(groq.id, "gpt-5")])
    assert caught.value.code == "unknown_model"

    # Bob sees nothing of Alice's, and cannot use her providers in his profile.
    assert settings.providers(bob) == []
    assert settings.profile(bob).entries == ()
    with pytest.raises(SettingsError) as caught:
        settings.set_profile(bob, [ProfileEntry(local.id, "qwen2.5:1.5b-instruct")])
    assert caught.value.code == "unknown_provider"
    assert not settings.delete_provider(bob, local.id)

    # Removing a provider removes it from the profile.
    assert settings.delete_provider(alice, groq.id)
    assert [e.model for e in settings.profile(alice).entries] == ["qwen2.5:1.5b-instruct"]


@requires_database
def test_the_worker_opens_the_key_of_its_user_only(
    migrated: TestDatabase, keys: tuple[X25519PrivateKey, Path], tmp_path: Path
) -> None:
    from otlet.ai.adapters.keys import SealedKeys

    private, public_file = keys
    private_file = tmp_path / "private.pem"
    private_file.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    engine = db.create_engine(migrated.app_url)
    settings = AiSettings(PostgresAiSettings(engine), CATALOGUE, PublicKeySealer(public_file))
    alice, bob = user(engine, "alice@example.org"), user(engine, "bob@example.org")
    groq = settings.add_provider(
        alice, name="Groq", kind="groq", endpoint=None, api_key="gsk-secret-123456"
    )
    with pytest.raises(SettingsError) as caught:  # localhost, not allowed by the administrator
        settings.add_provider(alice, name="Local", kind="ollama", endpoint=None, api_key=None)
    assert caught.value.code == "address_not_allowed"
    local = settings.add_provider(
        alice, name="Local", kind="ollama", endpoint="http://ollama:11434/v1", api_key=None
    )
    opener = SealedKeys(engine, private_file)
    assert opener.open(alice, groq.id) == "gsk-secret-123456"
    assert opener.open(alice, local.id) is None
    assert opener.open(bob, groq.id) is None  # not his provider
    from otlet.platform.secrets import PrivateKeyUnavailable

    with pytest.raises(PrivateKeyUnavailable):
        SealedKeys(engine, None).open(alice, groq.id)  # the API has no private key
