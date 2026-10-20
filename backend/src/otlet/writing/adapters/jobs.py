# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the writing module (U04).

- `writing.generate_draft`: the draft of a brief, written by the model it asks for.
"""

from uuid import UUID

from otlet.ai.adapters.catalogue_file import PackagedCatalogue
from otlet.ai.adapters.jobs import gateway
from otlet.ai.adapters.postgres import PostgresAiSettings
from otlet.jobs.application.registry import JobEnvironment, job
from otlet.writing.adapters.ai_writer import GatewayWriter
from otlet.writing.adapters.articles_postgres import PostgresArticleStore
from otlet.writing.adapters.charter_postgres import PostgresCharters
from otlet.writing.adapters.postgres import PostgresBriefStore
from otlet.writing.application.charter import Charters
from otlet.writing.application.drafts import GENERATE_DRAFT, Drafts


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
