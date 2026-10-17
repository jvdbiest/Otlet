# SPDX-License-Identifier: AGPL-3.0-or-later
"""« Tester » end to end, without the worker: a user's provider (a local fake of the OpenAI
protocol), their profile, the policy that lets the server reach it, the gateway with the real
stores, the sealed key opened as the worker would, the journal and the stored result."""

import ipaddress
import uuid
from pathlib import Path

import sqlalchemy as sa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ai_support import Fake
from integration_support import TestDatabase, requires_database
from otlet.ai.adapters.budget_postgres import PostgresBudget
from otlet.ai.adapters.catalogue_file import PackagedCatalogue
from otlet.ai.adapters.checks_postgres import PostgresChecks
from otlet.ai.adapters.journal_postgres import PostgresCallJournal
from otlet.ai.adapters.keys import SealedKeys
from otlet.ai.adapters.postgres import PostgresAiSettings
from otlet.ai.adapters.providers import adapter_factory
from otlet.ai.adapters.sealing import PublicKeySealer
from otlet.ai.application.budget import Budget
from otlet.ai.application.checks import CHECK_PROFILE, run_check
from otlet.ai.application.gateway import Gateway
from otlet.ai.application.settings import AiSettings
from otlet.ai.domain.settings import ProfileEntry
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.platform import database as db

pytestmark = requires_database


def test_a_check_runs_through_the_profile_and_is_journaled(
    migrated: TestDatabase, tmp_path: Path
) -> None:
    private = X25519PrivateKey.generate()
    public_file, private_file = tmp_path / "public.pem", tmp_path / "private.pem"
    public_file.write_bytes(
        private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    private_file.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    fake = Fake()
    fake.answer = '{"title": "Veille libre", "keywords": ["a", "b", "c"]}'
    try:
        engine = db.create_engine(migrated.app_url)
        alice: uuid.UUID = Authentication(
            PostgresIdentityStore(engine), Argon2Hasher()
        ).create_user("alice@example.org", "alice@example.org", "une phrase de passe assez longue")
        catalogue = PackagedCatalogue().load()
        store = PostgresAiSettings(engine)
        settings = AiSettings(store, catalogue, PublicKeySealer(public_file))
        settings.set_policy(
            is_admin=True,
            allowed_paid=[],
            networks=[str(ipaddress.ip_network("127.0.0.0/8"))],
            ports=[fake.port],
        )
        local = settings.add_provider(
            alice,
            name="Ollama du NAS",
            kind="ollama",
            endpoint=f"http://127.0.0.1:{fake.port}/v1",
            api_key=None,
        )
        settings.set_profile(
            alice,
            [ProfileEntry(local.id, "qwen2.5:1.5b-instruct"), ProfileEntry(local.id, "llama3.1")],
        )
        jobs: list[tuple[str, dict[str, str]]] = []

        def enqueue(connection: sa.Connection, name: str, **kwargs: str) -> int:
            jobs.append((name, kwargs))
            return len(jobs)

        checks = PostgresChecks(engine, enqueue)
        check = checks.create(alice, uuid.uuid4())
        assert jobs == [(CHECK_PROFILE, {"user_id": str(alice), "check_id": str(check.id)})]
        assert check.result is None
        journal = PostgresCallJournal(engine)
        gateway = Gateway(
            store,
            catalogue,
            SealedKeys(engine, private_file),
            Budget(PostgresBudget(engine)),
            adapter_factory,
            journal,
        )
        run_check(gateway, checks, alice, check.id)
        done = checks.get(alice, check.id)
        assert done is not None and done.finished_at is not None and done.result is not None
        assert done.result["ok"] is True, done.result
        assert done.result["answer"] == {"title": "Veille libre", "keywords": ["a", "b", "c"]}
        assert (done.result["provider"], done.result["model"]) == (
            "ollama",
            "qwen2.5:1.5b-instruct",
        )
        # Each model of the profile is tried in turn, even when the first one answers.
        assert [(m["model"], m["ok"]) for m in done.result["models"]] == [
            ("qwen2.5:1.5b-instruct", True),
            ("llama3.1", True),
        ]
        assert [r["body"]["model"] for r in fake.requests] == ["qwen2.5:1.5b-instruct", "llama3.1"]
        calls = journal.recent(alice)
        assert [(c["result"], c["provider_kind"]) for c in calls] == [("ok", "ollama")] * 2
        sent = fake.requests[-1]["body"]
        assert sent["response_format"]["json_schema"]["name"] == "check"
    finally:
        fake.server.shutdown()
