# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the meaning module (ADR-0045).

- `meaning.encode_pending`, every ten minutes: encodes the items without a vector, the most
  recent first, within a time budget.
"""

from otlet.jobs.application.registry import MAINTENANCE_QUEUE, JobEnvironment, job
from otlet.meaning.adapters.encoder import OnnxEncoder, release_memory
from otlet.meaning.adapters.postgres import PostgresMeaningStore
from otlet.meaning.application.meaning import ENCODE_PENDING, Meaning


@job(ENCODE_PENDING, queue=MAINTENANCE_QUEUE, cron="*/10 * * * *", attempts=1)
def encode_pending(environment: JobEnvironment) -> None:
    try:
        Meaning(PostgresMeaningStore(environment.engine), OnnxEncoder).encode_pending()
    finally:
        release_memory()
