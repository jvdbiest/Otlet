# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the writing module (U04).

- `writing.generate_draft`: the draft of a brief, written by the model it asks for.
- `writing.check_proximity`: how close a version is to its sources (U05, ADR-0046).
"""

from collections.abc import Sequence
from uuid import UUID

from otlet.ai.adapters.catalogue_file import PackagedCatalogue
from otlet.ai.adapters.jobs import gateway
from otlet.ai.adapters.postgres import PostgresAiSettings
from otlet.jobs.application.registry import JobEnvironment, job
from otlet.meaning.adapters.encoder import OnnxEncoder, release_memory
from otlet.writing.adapters.ai_writer import GatewayWriter
from otlet.writing.adapters.articles_postgres import PostgresArticleStore
from otlet.writing.adapters.charter_postgres import PostgresCharters
from otlet.writing.adapters.postgres import PostgresBriefStore
from otlet.writing.application.charter import Charters
from otlet.writing.application.drafts import GENERATE_DRAFT, Drafts
from otlet.writing.application.proximity import CHECK_PROXIMITY, run_check
from otlet.writing.domain.proximity import Encode


# One attempt: the gateway already retries and falls back; a second run would call (and pay)
# the providers again. A failed generation says why, and the user starts another.
@job(GENERATE_DRAFT, attempts=1)
def generate_draft(
    environment: JobEnvironment, workspace_id: str, user_id: str, generation_id: str
) -> None:
    engine = environment.engine
    writer = GatewayWriter(
        gateway(environment), PostgresAiSettings(engine), PackagedCatalogue().load()
    )
    charters = Charters(PostgresCharters(engine))
    Drafts(
        PostgresBriefStore(engine),
        PostgresArticleStore(engine, environment.enqueue),
        writer,
        lambda user: charters.of(user).text,
    ).run(UUID(workspace_id), UUID(user_id), UUID(generation_id))


# One attempt: a check that fails says so on the version, and is not run again by itself.
@job(CHECK_PROXIMITY, attempts=1)
def check_proximity(
    environment: JobEnvironment, workspace_id: str, article_id: str, number: int
) -> None:
    held: list[OnnxEncoder] = []

    def encoder() -> Encode:
        # Loaded only when there is something to check; let go after (some 700 MB).
        held.append(OnnxEncoder())

        def encode(texts: Sequence[str]) -> list[list[float]]:
            return held[0].encode(texts)

        return encode

    try:
        run_check(
            PostgresArticleStore(environment.engine, environment.enqueue),
            encoder,
            UUID(workspace_id),
            UUID(article_id),
            number,
        )
    finally:
        held.clear()
        release_memory()
