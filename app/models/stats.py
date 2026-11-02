"""What `GET /stats` returns."""

from __future__ import annotations

from datetime import datetime

from app.models.common import ApiModel


class Stats(ApiModel):
    """How much is published on the platform right now, one count per public collection."""

    blogs: int
    projects: int
    events: int
    videos: int
    experiences: int
    educations: int
    tools: int
    communities: int
    pillars: int
    speaking_topics: int
    comments: int
    generated_at: datetime
