# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the watch (U02): topics, the items of a topic with their explained scores, the
topics and duplicates of an item, and the search. All live under a workspace (F03)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from otlet.entrypoints.api.auth import same_origin
from otlet.entrypoints.api.collection import ItemView
from otlet.entrypoints.api.triage import TopicTagView, TriageView
from otlet.entrypoints.api.workspaces import PREFIX
from otlet.watch.application.watch import Watch
from otlet.watch.domain import model
from otlet.watch.domain.model import Contribution, Topic, WatchError
from otlet.watch.domain.triage import TopicFilter
from otlet.workspaces.domain.model import WorkspaceContext


class TopicView(BaseModel):
    id: str
    name: str
    description: str
    keywords: list[str]
    exclusions: list[str]
    languages: list[str]
    source_ids: list[str]
    created_at: datetime
    item_count: int
    rescoring: bool
    rescored_at: datetime | None

    @classmethod
    def of(cls, topic: Topic) -> "TopicView":
        return cls(
            id=str(topic.id),
            name=topic.name,
            description=topic.description,
            keywords=list(topic.keywords),
            exclusions=list(topic.exclusions),
            languages=list(topic.languages),
            source_ids=[str(source) for source in topic.source_ids],
            created_at=topic.created_at,
            item_count=topic.item_count,
            rescoring=topic.rescoring,
            rescored_at=topic.rescored_at,
        )


class TopicBody(BaseModel):
    name: str = Field(min_length=1, max_length=model.NAME_MAX_LENGTH)
    description: str = Field(default="", max_length=model.DESCRIPTION_MAX_LENGTH)
    # The limits of the domain (model.TERMS_MAX) answer with their own codes; these only bound
    # the size of a request.
    keywords: list[str] = Field(max_length=1000)
    exclusions: list[str] = Field(default_factory=list, max_length=1000)
    languages: list[str] = Field(default_factory=list, max_length=len(model.LANGUAGES))
    source_ids: list[UUID] = Field(default_factory=list, max_length=500)


class ContributionView(BaseModel):
    term: str
    where: str
    count: int
    points: int

    @classmethod
    def of(cls, contribution: Contribution) -> "ContributionView":
        return cls(
            term=contribution.term,
            where=contribution.where,
            count=contribution.count,
            points=contribution.points,
        )


class ScoredItemView(BaseModel):
    item: ItemView
    score: int
    freshness: int
    contributions: list[ContributionView]
    triage: TriageView


class ItemTopicView(BaseModel):
    topic_id: str
    name: str
    score: int
    contributions: list[ContributionView]


class DuplicateView(BaseModel):
    item_id: str
    title: str
    source_name: str | None
    url: str | None


class ItemWatchView(BaseModel):
    topics: list[ItemTopicView]
    duplicates: list[DuplicateView]


class RefreshView(BaseModel):
    sources: int
    topics: int


class FoundItemView(BaseModel):
    item: ItemView
    rank: float
    triage: TriageView
    topics: list[TopicTagView]  # best score first: the first is the main topic


def _refused(error: WatchError) -> HTTPException:
    code = (
        status.HTTP_409_CONFLICT
        if error.code == "name_taken"
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return HTTPException(code, error.code)


def build_router(watch: Watch, workspace_context: Callable[..., WorkspaceContext]) -> APIRouter:
    Context = Annotated[WorkspaceContext, Depends(workspace_context)]
    router = APIRouter(prefix=PREFIX + "/{workspace_id}", dependencies=[Depends(same_origin)])

    @router.get("/topics")
    def list_topics(context: Context) -> list[TopicView]:
        return [TopicView.of(topic) for topic in watch.list_topics(context)]

    @router.post("/topics", status_code=status.HTTP_201_CREATED)
    def create_topic(body: TopicBody, context: Context) -> TopicView:
        try:
            return TopicView.of(watch.create_topic(context, **body.model_dump()))
        except WatchError as error:
            raise _refused(error) from error

    @router.get("/topics/{topic_id}")
    def get_topic(topic_id: UUID, context: Context) -> TopicView:
        topic = watch.get_topic(context, topic_id)
        if topic is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "topic_not_found")
        return TopicView.of(topic)

    @router.put("/topics/{topic_id}")
    def update_topic(topic_id: UUID, body: TopicBody, context: Context) -> TopicView:
        try:
            topic = watch.update_topic(context, topic_id, **body.model_dump())
        except WatchError as error:
            raise _refused(error) from error
        if topic is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "topic_not_found")
        return TopicView.of(topic)

    @router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_topic(topic_id: UUID, context: Context) -> None:
        if not watch.delete_topic(context, topic_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "topic_not_found")

    @router.post("/topics/{topic_id}/rescore", status_code=status.HTTP_202_ACCEPTED)
    def rescore_topic(topic_id: UUID, context: Context) -> None:
        """Matches the topic again with the recent items, in the background."""
        if not watch.rescore(context, topic_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "topic_not_found")

    @router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
    def refresh(context: Context) -> RefreshView:
        """Collects every active source now and matches every topic again."""
        sources, topics = watch.refresh(context)
        return RefreshView(sources=sources, topics=topics)

    @router.get("/topics/{topic_id}/items")
    def topic_items(
        topic_id: UUID,
        context: Context,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
    ) -> list[ScoredItemView]:
        """The items of a topic, best score first; the score is explained (F-VEI-02)."""
        if watch.get_topic(context, topic_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "topic_not_found")
        scored = watch.topic_items(context, topic_id, datetime.now(UTC), limit=limit, offset=offset)
        return [
            ScoredItemView(
                item=ItemView.of(entry.item, with_text=False),
                score=entry.score,
                freshness=entry.freshness,
                contributions=[ContributionView.of(c) for c in entry.contributions],
                triage=TriageView.of(entry.triage),
            )
            for entry in scored
        ]

    @router.get("/items/{item_id}/watch")
    def item_watch(item_id: UUID, context: Context) -> ItemWatchView:
        """The topics of an item, with their explained scores, and the same story elsewhere."""
        return ItemWatchView(
            topics=[
                ItemTopicView(
                    topic_id=str(found.topic_id),
                    name=found.name,
                    score=found.score,
                    contributions=[ContributionView.of(c) for c in found.contributions],
                )
                for found in watch.item_topics(context, item_id)
            ],
            duplicates=[
                DuplicateView(
                    item_id=str(d.item_id), title=d.title, source_name=d.source_name, url=d.url
                )
                for d in watch.duplicates(context, item_id)
            ],
        )

    @router.get("/search")
    def search(
        context: Context,
        q: Annotated[str, Query(min_length=1, max_length=200)],
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        topic_id: Annotated[list[UUID], Query(max_length=100)] = [],  # noqa: B006 (FastAPI copies it)
        all_topics: bool = False,
    ) -> list[FoundItemView]:
        """Full-text search of the items, best match first (ADR-0021: bounded ranking), within
        the chosen topics if any (as in the feed)."""
        try:
            found = watch.search(context, q, limit, TopicFilter(tuple(topic_id), all_topics))
        except WatchError as error:
            raise _refused(error) from error
        return [
            FoundItemView(
                item=ItemView.of(f.item, with_text=False),
                rank=f.rank,
                triage=TriageView.of(f.triage),
                topics=[TopicTagView.of(tag) for tag in f.topics],
            )
            for f in found
        ]

    return router
