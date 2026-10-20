# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the watch feed and its triage (X02): the feed of the user, the triage of an item,
and the progress of the first steps (FA §7.7). All live under a workspace (F03)."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.collection import ItemView
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.watch.application.triage import SELECTION_MAX, Change, Feed
from otlet.watch.domain.triage import (
    Decision,
    Group,
    GroupBy,
    InGroup,
    Period,
    Sort,
    TopicFilter,
    TopicTag,
    Triage,
    View,
)
from otlet.workspaces.domain.model import WorkspaceContext


class TriageView(BaseModel):
    decision: Literal["kept", "writing", "dismissed", "archived"] | None
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


class GroupView(BaseModel):
    key: UUID | None  # None: the items without topic, or the manual entries
    name: str
    count: int

    @classmethod
    def of(cls, group: Group) -> "GroupView":
        return cls(key=group.key, name=group.name, count=group.count)


class TriageChange(BaseModel):
    """A field left out keeps its value; `decision: null` clears the decision."""

    decision: Literal["kept", "writing", "dismissed", "archived"] | None = None
    pinned: bool | None = None
    read: bool | None = None


class BulkTriage(BaseModel):
    """One action of the feed for several items: keep, dismiss, archive, pin, or back to sort."""

    item_ids: list[UUID] = Field(min_length=1, max_length=SELECTION_MAX)
    action: Literal["keep", "dismiss", "archive", "pin", "to_sort"]


class BulkResult(BaseModel):
    changed: int


BULK_CHANGES = {
    "keep": Change(decision=Decision.KEPT),
    "dismiss": Change(decision=Decision.DISMISSED),
    "archive": Change(decision=Decision.ARCHIVED),
    "pin": Change(pinned=True),
    "to_sort": Change(clear_decision=True),
}


class ProgressView(BaseModel):
    sources: int
    topics: int
    decisions: int


def period_of(since: datetime | None, until: datetime | None) -> Period:
    """The period of a request, refused when it ends before it starts."""
    period = Period(since, until)
    if not period.valid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_period")
    return period


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
        since: datetime | None = None,
        until: datetime | None = None,
        sort: Sort = Sort.DATE,
        group_by: GroupBy | None = None,
        group: UUID | None = None,
    ) -> list[FeedItemView]:
        """The feed of the user: pinned items first (except for `all`), then in the order of
        `sort`; `before` (the id of the last item of the previous page) pages back.
        `topic_id`, repeated, keeps the items of at least one of these topics, or of all of
        them with `all_topics`; `since` and `until` keep the items dated in between;
        `group_by` with `group` keeps one group of `/feed/groups` (no `group`: the items
        without topic, or the manual entries)."""
        items = feed.feed(
            context,
            view=view,
            source_id=source_id,
            unread_only=unread,
            before=before,
            limit=limit,
            topics=TopicFilter(tuple(topic_id), all_topics),
            period=period_of(since, until),
            sort=sort,
            group=None if group_by is None else InGroup(group_by, group),
        )
        return [
            FeedItemView(
                item=ItemView.of(f.item, with_text=False),
                triage=TriageView.of(f.triage),
                topics=[TopicTagView.of(tag) for tag in f.topics],
            )
            for f in items
        ]

    @router.get("/feed/ids")
    def feed_ids(
        context: Context,
        view: View = View.TO_SORT,
        source_id: UUID | None = None,
        unread: bool = False,
        topic_id: Annotated[list[UUID], Query(max_length=100)] = [],  # noqa: B006 (FastAPI copies it)
        all_topics: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[UUID]:
        """« Tout sélectionner »: the ids of every item the feed shows with these filters, over
        all its pages and groups (5000 at most)."""
        return feed.ids(
            context,
            view=view,
            source_id=source_id,
            unread_only=unread,
            topics=TopicFilter(tuple(topic_id), all_topics),
            period=period_of(since, until),
        )

    @router.get("/feed/groups")
    def feed_groups(
        context: Context,
        by: GroupBy,
        view: View = View.TO_SORT,
        source_id: UUID | None = None,
        unread: bool = False,
        topic_id: Annotated[list[UUID], Query(max_length=100)] = [],  # noqa: B006 (FastAPI copies it)
        all_topics: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[GroupView]:
        """The groups of the feed, by main topic or by source, with the same filters as
        `/feed`, and how many items each holds; the group without key comes last."""
        groups = feed.groups(
            context,
            by=by,
            view=view,
            source_id=source_id,
            unread_only=unread,
            topics=TopicFilter(tuple(topic_id), all_topics),
            period=period_of(since, until),
        )
        return [GroupView.of(group) for group in groups]

    @router.post("/items/triage")
    def change_many(body: BulkTriage, context: Context) -> BulkResult:
        return BulkResult(
            changed=feed.change_many(context, body.item_ids, BULK_CHANGES[body.action])
        )

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
