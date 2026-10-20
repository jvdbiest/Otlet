# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the collection module (U01).

- `collection.collect_source`: one run of one source, in its workspace.
- `collection.extract_item`: reads the page of one new item, in its workspace.
"""

from uuid import UUID

from otlet.collection.adapters.parsing import FeedparserReader, ReadabilityReader
from otlet.collection.adapters.postgres import PostgresCollectionStore
from otlet.collection.application.collection import (
    COLLECT_SOURCE,
    EXTRACT_DECLARED,
    EXTRACT_ITEM,
    Collection,
)
from otlet.jobs.application.registry import JobEnvironment, job
from otlet.platform.http import SafeClient


def collection(environment: JobEnvironment, client: SafeClient) -> Collection:
    store = PostgresCollectionStore(environment.engine, environment.enqueue)
    return Collection(store, client, FeedparserReader(), ReadabilityReader())


# A failed run is not retried at once: the next interval retries it, with a growing delay.
@job(COLLECT_SOURCE, attempts=1)
def collect_source(environment: JobEnvironment, workspace_id: str, source_id: str) -> None:
    with SafeClient() as client:
        collection(environment, client).collect(UUID(workspace_id), UUID(source_id))


@job(EXTRACT_DECLARED, attempts=3)
def extract_declared(environment: JobEnvironment, workspace_id: str, item_id: str) -> None:
    with SafeClient() as client:
        collection(environment, client).extract_declared(UUID(workspace_id), UUID(item_id))


@job(EXTRACT_ITEM, attempts=3)
def extract_item(environment: JobEnvironment, workspace_id: str, item_id: str) -> None:
    with SafeClient() as client:
        collection(environment, client).extract(UUID(workspace_id), UUID(item_id))
