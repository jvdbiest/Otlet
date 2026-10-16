# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of the watch module (U02).

- `watch.item_ready`: an item the collection has finished is compared with the earlier items
  (duplicates) and matched with the topics of its workspace.
- `watch.rescore_topic`: a created or changed topic is matched with the recent items.
- `watch.catch_up`, every five minutes: handles again the items whose event was lost.
"""

from datetime import UTC, datetime
from uuid import UUID

from otlet.jobs.application.registry import MAINTENANCE_QUEUE, JobEnvironment, job
from otlet.watch.adapters.postgres import PostgresWatchStore
from otlet.watch.application.watch import CATCH_UP, ITEM_READY, RESCORE_TOPIC, Watch


def watch(environment: JobEnvironment) -> Watch:
    return Watch(PostgresWatchStore(environment.engine, environment.enqueue))


@job(ITEM_READY, attempts=3)
def item_ready(environment: JobEnvironment, workspace_id: str, item_id: str) -> None:
    watch(environment).item_ready(UUID(workspace_id), UUID(item_id))


@job(RESCORE_TOPIC, attempts=3)
def rescore_topic(environment: JobEnvironment, workspace_id: str, topic_id: str) -> None:
    watch(environment).rescore_topic(UUID(workspace_id), UUID(topic_id), datetime.now(UTC))


# Maintenance (ADR-0030): a repair of lost events, not a deadline of the domain.
@job(CATCH_UP, queue=MAINTENANCE_QUEUE, cron="*/5 * * * *", attempts=1)
def catch_up(environment: JobEnvironment) -> None:
    watch(environment).catch_up()
