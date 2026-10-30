# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the meaning module (ADR-0045).

- `meaning.encode_pending`, every ten minutes: encodes the items without a vector, the most
  recent first, within a time budget.
"""

import ctypes
import gc

from otlet.jobs.application.registry import MAINTENANCE_QUEUE, JobEnvironment, job
from otlet.meaning.adapters.encoder import OnnxEncoder
from otlet.meaning.adapters.postgres import PostgresMeaningStore
from otlet.meaning.application.meaning import ENCODE_PENDING, Meaning


def release_memory() -> None:
    """Gives the memory of the model back to the system once the run is over: freed memory
    otherwise stays with the worker, which lives on between runs."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except OSError:  # not glibc
        pass


@job(ENCODE_PENDING, queue=MAINTENANCE_QUEUE, cron="*/10 * * * *", attempts=1)
def encode_pending(environment: JobEnvironment) -> None:
    try:
        Meaning(PostgresMeaningStore(environment.engine), OnnxEncoder).encode_pending()
    finally:
        release_memory()
