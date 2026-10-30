# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the Reporter (A2-1).

- `reporter.answer_turn`: the operation of a question, its set, and the lines of a fact.
"""

from uuid import UUID

from otlet.ai.adapters.jobs import gateway
from otlet.assistant.adapters.ai_model import GatewayModel
from otlet.assistant.adapters.postgres import PostgresAssistantStore
from otlet.jobs.application.registry import JobEnvironment, job
from otlet.meaning.adapters.encoder import encode_question
from otlet.reporter.adapters.postgres import PostgresReporterStore
from otlet.reporter.application.reporter import ANSWER_TURN, Reporter

USAGE = "reporter"


# One attempt: the gateway already retries and falls back; a question the model could not
# translate is marked failed, and the author asks it again.
@job(ANSWER_TURN, attempts=1)
def answer_turn(
    environment: JobEnvironment,
    workspace_id: str,
    user_id: str,
    conversation_id: str,
    turn_id: str,
) -> None:
    store = PostgresReporterStore(environment.engine, environment.enqueue)
    search = PostgresAssistantStore(environment.engine)
    workspace, turn = UUID(workspace_id), UUID(turn_id)
    model = GatewayModel(
        gateway(environment), USAGE, cancelled=lambda: not store.is_pending(workspace, turn)
    )
    Reporter(store, search, model, encode=encode_question).run(
        workspace, UUID(user_id), UUID(conversation_id), turn
    )
