# SPDX-License-Identifier: AGPL-3.0-or-later
"""The proximity check of a version (U05, ADR-0046): run by the worker after each generation and
each save, read at validation and at export. A version too close to a source does not go out
unless its author says why (Joël, 2026-11-01): a false alarm must not force a rewrite."""

import logging
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.domain.document import plain_text
from otlet.writing.domain.proximity import (
    JUSTIFICATION_MAX,
    JUSTIFICATION_MIN,
    Encode,
    Gate,
    Source,
    check,
)

CHECK_PROXIMITY = "writing.check_proximity"
logger = logging.getLogger(__name__)


class JustificationError(ValueError):
    pass


class ProximityStore(Protocol):
    def gate(self, workspace_id: UUID, article_id: UUID, number: int) -> Gate:
        """Whether the version can go out; one never checked is checked now."""
        ...

    def to_check(
        self, workspace_id: UUID, article_id: UUID, number: int
    ) -> tuple[str, dict[str, Any], list[Source]] | None:
        """The title, document and sources of a version not checked yet; None for any other."""
        ...

    def save_proximity(
        self, workspace_id: UUID, article_id: UUID, number: int, report: dict[str, Any]
    ) -> None: ...

    def override_proximity(
        self, workspace_id: UUID, user_id: UUID, article_id: UUID, number: int, reason: str
    ) -> bool:
        """Keeps the author's justification, with who and when; False without such a version."""
        ...


def run_check(
    store: ProximityStore,
    encoder: Callable[[], Encode],
    workspace_id: UUID,
    article_id: UUID,
    number: int,
) -> None:
    """The job. `encoder` loads the model, only when there is something to check."""
    found = store.to_check(workspace_id, article_id, number)
    if found is None:
        return
    title, document, sources = found
    paragraphs = [plain_text(block) for block in document.get("content", [])]
    language = document.get("attrs", {}).get("langue")
    try:
        report = check(title, paragraphs, language, sources, encoder())
    except Exception:
        logger.exception("proximity check failed", extra={"article": str(article_id)})
        report = {"status": "failed", "blocked": False, "sources": []}
    store.save_proximity(workspace_id, article_id, number, report)


def override(
    store: ProximityStore, context: WorkspaceContext, article_id: UUID, number: int, reason: str
) -> bool:
    reason = " ".join(reason.split())
    if not JUSTIFICATION_MIN <= len(reason) <= JUSTIFICATION_MAX:
        raise JustificationError(
            f"a justification has {JUSTIFICATION_MIN} to {JUSTIFICATION_MAX} characters"
        )
    return store.override_proximity(
        context.workspace_id, context.user_id, article_id, number, reason
    )
