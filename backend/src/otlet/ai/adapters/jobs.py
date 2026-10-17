# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the AI gateway (F05). They run in the worker, the only process with the
private key that opens the keys of providers (DR6).

- `ai.check_profile`: « Tester » — one small structured answer through the user's profile.
"""

from uuid import UUID

from otlet.ai.adapters.budget_postgres import PostgresBudget
from otlet.ai.adapters.catalogue_file import PackagedCatalogue
from otlet.ai.adapters.checks_postgres import PostgresChecks
from otlet.ai.adapters.journal_postgres import PostgresCallJournal
from otlet.ai.adapters.keys import SealedKeys
from otlet.ai.adapters.postgres import PostgresAiSettings
from otlet.ai.adapters.providers import adapter_factory
from otlet.ai.application.budget import Budget
from otlet.ai.application.checks import CHECK_PROFILE, run_check
from otlet.ai.application.gateway import Gateway
from otlet.jobs.application.registry import JobEnvironment, job


def gateway(environment: JobEnvironment) -> Gateway:
    engine = environment.engine
    return Gateway(
        PostgresAiSettings(engine),
        PackagedCatalogue().load(),
        SealedKeys(engine, environment.secrets_private_key_file),
        Budget(PostgresBudget(engine)),
        adapter_factory,
        PostgresCallJournal(engine),
    )


# One attempt: the gateway already retries and falls back; a second run would call (and pay)
# the providers again.
@job(CHECK_PROFILE, attempts=1)
def check_profile(environment: JobEnvironment, user_id: str, check_id: str) -> None:
    run_check(
        gateway(environment),
        PostgresChecks(environment.engine, environment.enqueue),
        UUID(user_id),
        UUID(check_id),
    )
