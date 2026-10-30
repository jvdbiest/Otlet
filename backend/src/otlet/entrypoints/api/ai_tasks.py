# SPDX-License-Identifier: AGPL-3.0-or-later
"""The AI work under way for a user, in every module (Joël, 2026-10-30): « Tâche(s) IA en cours »
and « Annuler toute génération en cours ». Each module keeps its own state: nothing is copied."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from otlet.ai.application.checks import CANCELLED, CheckStore
from otlet.assistant.application.dossiers import Dossiers
from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.reporter.application.reporter import Reporter
from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.application.drafts import Drafts


class AiTaskView(BaseModel):
    kind: Literal["reporter", "dossier", "draft", "check"]
    id: UUID  # the conversation, the dossier, the brief or the check
    label: str
    started_at: datetime | None


class CancelledView(BaseModel):
    cancelled: int


def build_router(
    reporter: Reporter,
    dossiers: Dossiers,
    drafts: Drafts,
    checks: CheckStore,
    workspace_context: Callable[..., WorkspaceContext],
) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(
        prefix=PREFIX + "/{workspace_id}/ai-tasks", dependencies=[Depends(same_origin)]
    )

    def running(context: WorkspaceContext) -> list[AiTaskView]:
        return [
            *(
                AiTaskView(
                    kind="reporter", id=t.conversation_id, label=t.question, started_at=t.created_at
                )
                for t in reporter.running(context)
            ),
            *(
                AiTaskView(kind="dossier", id=d.id, label=d.subject, started_at=d.created_at)
                for d in dossiers.running(context)
            ),
            *(
                AiTaskView(kind="draft", id=d.brief_id, label=d.title, started_at=d.created_at)
                for d in drafts.running(context)
            ),
            *(
                AiTaskView(kind="check", id=c.id, label="", started_at=c.created_at)
                for c in checks.running(context.user_id)
            ),
        ]

    @router.get("")
    def tasks(context: Context) -> list[AiTaskView]:
        return running(context)

    @router.post("/cancel")
    def cancel_all(context: Context) -> CancelledView:
        """Ends all of them; the worker cuts the calls to the models under way."""
        found = running(context)
        for task in found:
            if task.kind == "reporter":
                reporter.cancel(context, task.id)
            elif task.kind == "dossier":
                dossiers.cancel(context, task.id)
            elif task.kind == "draft":
                drafts.cancel(context, task.id)
            else:
                checks.finish(context.user_id, task.id, CANCELLED)
        return CancelledView(cancelled=len(found))

    return router
