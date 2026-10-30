# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the Assistant de veille (A1b-1).

- `assistant.qualify_dossier`: the concepts, the candidates and their verdicts of a dossier.
"""

from uuid import UUID

from otlet.ai.adapters.jobs import gateway
from otlet.assistant.adapters.ai_model import GatewayModel
from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.assistant.application.dossiers import QUALIFY_DOSSIER, Dossiers
from otlet.jobs.application.registry import JobEnvironment, job
from otlet.meaning.adapters.encoder import encode_question


# One attempt: the gateway already retries and falls back; a dossier the model could not
# finish still shows every candidate, « à vérifier ».
@job(QUALIFY_DOSSIER, attempts=1)
def qualify_dossier(
    environment: JobEnvironment, workspace_id: str, user_id: str, dossier_id: str
) -> None:
    store = PostgresAssistantStore(environment.engine, environment.enqueue)
    Dossiers(store, store, GatewayModel(gateway(environment)), encode=encode_question).run(
        UUID(workspace_id), UUID(user_id), UUID(dossier_id)
    )
