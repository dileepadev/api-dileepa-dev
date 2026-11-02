"""`GET /stats` — how much is published on the platform.

Public, read-only . It counts only what a signed-out visitor can
already see: the same `published: {$ne: false}` rule the list endpoints apply,
so a draft never moves a number. Nothing about a record leaves this route, only
how many there are.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.deps import repository
from app.models.stats import Stats
from app.repositories.base import DocumentRepository

router = APIRouter(prefix="/stats", tags=["stats"])

PUBLISHED = {"published": {"$ne": False}}

Blogs = Annotated[DocumentRepository, Depends(repository("blogs"))]
Projects = Annotated[DocumentRepository, Depends(repository("projects"))]
Events = Annotated[DocumentRepository, Depends(repository("events"))]
Videos = Annotated[DocumentRepository, Depends(repository("videos"))]
Experiences = Annotated[DocumentRepository, Depends(repository("experiences"))]
Educations = Annotated[DocumentRepository, Depends(repository("educations"))]
Tools = Annotated[DocumentRepository, Depends(repository("tools"))]
Communities = Annotated[DocumentRepository, Depends(repository("communities"))]
Pillars = Annotated[DocumentRepository, Depends(repository("pillars"))]
SpeakingTopics = Annotated[DocumentRepository, Depends(repository("speaking_topics"))]
Comments = Annotated[DocumentRepository, Depends(repository("comments"))]


@router.get("", response_model=Stats, summary="Counts of what is published")
async def read_stats(
    response: Response,
    blogs: Blogs,
    projects: Projects,
    events: Events,
    videos: Videos,
    experiences: Experiences,
    educations: Educations,
    tools: Tools,
    communities: Communities,
    pillars: Pillars,
    speaking_topics: SpeakingTopics,
    comments: Comments,
) -> Stats:
    """Published posts, projects, events, videos, experience, education, tools,
    communities, pillars, speaking topics and visible comments.

    Cached for a minute by the client or the edge, so a busy page does not turn
    into eleven database counts per visitor.
    """
    response.headers["Cache-Control"] = "public, max-age=60"
    return Stats(
        blogs=await blogs.count(PUBLISHED),
        projects=await projects.count(PUBLISHED),
        events=await events.count(PUBLISHED),
        videos=await videos.count(PUBLISHED),
        experiences=await experiences.count(PUBLISHED),
        educations=await educations.count(PUBLISHED),
        tools=await tools.count(PUBLISHED),
        communities=await communities.count(PUBLISHED),
        pillars=await pillars.count(PUBLISHED),
        speaking_topics=await speaking_topics.count(PUBLISHED),
        comments=await comments.count(PUBLISHED),
        generated_at=datetime.now(UTC),
    )
