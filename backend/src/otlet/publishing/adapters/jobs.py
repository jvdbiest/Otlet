# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background jobs of publishing (U07). They run in the worker, the only process with the
private key that opens the passwords of the sites (DR6).

- `publishing.check_site`: « Tester » — the account, its role, the categories and tags.
- `publishing.send`: one send of an article, as a draft or published.
"""

from typing import Any
from uuid import UUID

from otlet.ai.adapters.postgres import PostgresAiSettings
from otlet.ai.adapters.providers import address_policy
from otlet.jobs.application.registry import JobEnvironment, job
from otlet.platform.secrets import SecretError
from otlet.platform.secrets.opening import load_private_key, open_sealed
from otlet.publishing.adapters.postgres import PostgresPublishing, PostgresValidated
from otlet.publishing.adapters.wordpress import WordPress
from otlet.publishing.application.publishing import (
    CHECK_SITE,
    SEND,
    Remote,
    SiteError,
    password_context,
    run_check,
    run_send,
)
from otlet.publishing.domain.model import Site
from otlet.writing.adapters.articles_postgres import PostgresArticleStore
from otlet.writing.domain.document import render


def content(title: str, document: Any) -> tuple[str, str]:
    """The title and the HTML of a version for WordPress: its blocks, the AI mention and the
    Sources block, as the exports render them; the theme of the site decides the look. Images
    come in a later version: they are left out."""
    kept = {**document, "content": [b for b in document["content"] if b.get("type") != "image"]}
    return title, render(kept, publication=True)


def _remote(environment: JobEnvironment, store: PostgresPublishing) -> Any:
    policy = address_policy(PostgresAiSettings(environment.engine).policy())

    def connect(site: Site) -> Remote:
        sealed = store.password(site.workspace_id, site.id)
        if sealed is None:
            raise SiteError("site_not_found")
        try:
            private_key = load_private_key(environment.secrets_private_key_file)
            password = open_sealed(private_key, sealed, password_context(site.id)).decode()
        except SecretError as error:  # a missing or wrong key: say so on the site
            raise SiteError("secrets_unavailable", type(error).__name__) from error
        return WordPress(site.url, site.username, password, policy)

    return connect


# One attempt: a check that fails says why on the site; the author tests again.
@job(CHECK_SITE, attempts=1)
def check_site(environment: JobEnvironment, workspace_id: str, site_id: str) -> None:
    store = PostgresPublishing(environment.engine, environment.enqueue)
    run_check(store, _remote(environment, store), UUID(workspace_id), UUID(site_id))


# One attempt: a send that fails says why, after looking for the post (ADR-0026 §2); sending
# again is the author's choice.
@job(SEND, attempts=1)
def send(environment: JobEnvironment, workspace_id: str, publication_id: str, user_id: str) -> None:
    store = PostgresPublishing(environment.engine, environment.enqueue)
    articles = PostgresValidated(
        environment.engine, PostgresArticleStore(environment.engine, environment.enqueue).gate
    )
    run_send(
        store,
        articles,
        content,
        _remote(environment, store),
        UUID(workspace_id),
        UUID(publication_id),
        UUID(user_id),
    )
