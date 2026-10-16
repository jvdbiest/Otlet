# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the watch feed and its triage (X02): the feed of the user, the triage of an item,
and the progress of the first steps (FA §7.7). All live under a workspace (F03)."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.collection import ItemView
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.watch.application.triage import Change, Feed
from otlet.watch.domain.triage import Decision, TopicFilter, TopicTag, Triage, View
from otlet.workspaces.domain.model import WorkspaceContext


class TriageView(BaseModel):
    decision: Literal["kept", "dismissed"] | None
    pinned: bool
    read_at: datetime | None

    @classmethod
    def of(cls, triage: Triage) -> "TriageView":
        return cls(
            decision=None if triage.decision is None else triage.decision.value,
            pinned=triage.pinned,
            read_at=triage.read_at,
        )


class TopicTagView(BaseModel):
    id: UUID
    name: str
    score: int

    @classmethod
    def of(cls, tag: TopicTag) -> "TopicTagView":
        return cls(id=tag.id, name=tag.name, score=tag.score)


class FeedItemView(BaseModel):
    item: ItemView
    triage: TriageView
    topics: list[TopicTagView]  # best score first: the first is the main topic


class TriageChange(BaseModel):
    """A field left out keeps its value; `decision: null` clears the decision."""

    decision: Literal["kept", "dismissed"] | None = None
    pinned: bool | None = None
    read: bool | None = None


class ProgressView(BaseModel):
    sources: int
    topics: int
    decisions: int


def build_router(feed: Feed, workspace_context: Callable[..., WorkspaceContext]) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(prefix=PREFIX + "/{workspace_id}", dependencies=[Depends(same_origin)])

    @router.get("/feed")
    def get_feed(
        context: Context,
        view: View = View.TO_SORT,
        source_id: UUID | None = None,
        unread: bool = False,
        before: UUID | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        topic_id: Annotated[list[UUID], Query(max_length=100)] = [],  # noqa: B006 (FastAPI copies it)
        all_topics: bool = False,
    ) -> list[FeedItemView]:
        """The feed of the user: pinned items first, then the most recent; `before` (the id of
        the last item of the previous page) pages back. `topic_id`, repeated, keeps the items of
        at least one of these topics, or of all of them with `all_topics`."""
        items = feed.feed(
            context,
            view=view,
            source_id=source_id,
            unread_only=unread,
            before=before,
            limit=limit,
            topics=TopicFilter(tuple(topic_id), all_topics),
        )
        return [
            FeedItemView(
                item=ItemView.of(f.item, with_text=False),
                triage=TriageView.of(f.triage),
                topics=[TopicTagView.of(tag) for tag in f.topics],
            )
            for f in items
        ]

    @router.get("/items/{item_id}/triage")
    def get_triage(item_id: UUID, context: Context) -> TriageView:
        triage = feed.triage(context, item_id)
        if triage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")
        return TriageView.of(triage)

    @router.patch("/items/{item_id}/triage")
    def change_triage(item_id: UUID, body: TriageChange, context: Context) -> TriageView:
        given = body.model_fields_set
        change = Change(
            decision=None if body.decision is None else Decision(body.decision),
            clear_decision="decision" in given and body.decision is None,
            pinned=body.pinned,
            read=body.read,
        )
        triage = feed.change(context, item_id, change)
        if triage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "item_not_found")
        return TriageView.of(triage)

    @router.get("/progress")
    def progress(context: Context) -> ProgressView:
        """How far the user went in the first steps: sources, topics, first decisions."""
        found = feed.progress(context)
        return ProgressView(sources=found.sources, topics=found.topics, decisions=found.decisions)

    return router
