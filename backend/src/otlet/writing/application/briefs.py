# SPDX-License-Identifier: AGPL-3.0-or-later
"""Briefs of a workspace (U03, F-RED-01, UC « rédiger un article » steps 1 to 3).

The items of a new brief, and the items added to a brief, move to drafting in the triage of
its author: the flow of an item is to sort, kept, drafting, archived (Joël, 2026-10-17). The
watch module owns the triage; the composition of the application passes how to mark them.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from typing import Protocol
from uuid import UUID

from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.domain.brief import Brief, BriefFields, Length, Mode, ModelChoice, Nature
from otlet.writing.domain.matter import Evaluation, MatterItem, evaluate

# Moves items to drafting in the triage of the user of the context.
MarkWriting = Callable[[WorkspaceContext, Sequence[UUID]], object]
# Refuses (by raising) a model the user may not use: not theirs, unknown or blocked.
CheckModel = Callable[[UUID, ModelChoice], None]


class BriefStore(Protocol):
    def list_briefs(self, workspace_id: UUID) -> list[Brief]:
        """The briefs of the workspace, the most recently changed first."""
        ...

    def get_brief(self, workspace_id: UUID, brief_id: UUID) -> Brief | None: ...

    def create_brief(self, workspace_id: UUID, user_id: UUID, fields: BriefFields) -> Brief:
        """Raises BriefError `unknown_item` when an item is not in the workspace, and
        `unknown_provider` when the provider is not one of the user's."""
        ...

    def update_brief(self, workspace_id: UUID, brief_id: UUID, fields: BriefFields) -> Brief | None:
        """As create_brief; None when the brief does not exist."""
        ...

    def delete_brief(self, workspace_id: UUID, brief_id: UUID) -> bool: ...

    def matter_items(self, workspace_id: UUID, item_ids: list[UUID]) -> list[MatterItem]:
        """The items of the workspace among `item_ids`, in that order; others are left out."""
        ...


class Briefs:
    def __init__(
        self, store: BriefStore, mark_writing: MarkWriting, check_model: CheckModel
    ) -> None:
        self._store = store
        self._mark_writing = mark_writing
        self._check_model = check_model

    def list(self, context: WorkspaceContext) -> list[Brief]:
        return self._store.list_briefs(context.workspace_id)

    def get(self, context: WorkspaceContext, brief_id: UUID) -> Brief | None:
        return self._store.get_brief(context.workspace_id, brief_id)

    def matter(
        self,
        context: WorkspaceContext,
        item_ids: Sequence[UUID],
        length: Length,
        mode: Mode,
        nature: Nature,
        today: date | None = None,
    ) -> Evaluation:
        """The matter of a brief as it is being written, saved or not (ADR-0041)."""
        items = self._store.matter_items(context.workspace_id, [*item_ids])
        return evaluate(items, length, mode, nature, today or datetime.now(UTC).date())

    def create(self, context: WorkspaceContext, fields: BriefFields) -> Brief:
        checked = self._checked(context, fields)
        brief = self._store.create_brief(context.workspace_id, context.user_id, checked)
        self._mark_writing(context, checked.item_ids)
        return brief

    def update(
        self, context: WorkspaceContext, brief_id: UUID, fields: BriefFields
    ) -> Brief | None:
        checked = self._checked(context, fields)
        before = self._store.get_brief(context.workspace_id, brief_id)
        if before is None:
            return None
        brief = self._store.update_brief(context.workspace_id, brief_id, checked)
        added = [i for i in checked.item_ids if i not in before.fields.item_ids]
        if brief is not None and added:
            self._mark_writing(context, added)
        return brief

    def delete(self, context: WorkspaceContext, brief_id: UUID) -> bool:
        """The items keep their triage: drafting, until their author sorts them again."""
        return self._store.delete_brief(context.workspace_id, brief_id)

    def _checked(self, context: WorkspaceContext, fields: BriefFields) -> BriefFields:
        checked = fields.checked()
        if checked.model is not None:
            self._check_model(context.user_id, checked.model)
        return checked
