"""Sessions — net-new in v2.0.0, superseding `events`.

`events` carried seven fields: title, date (string), location, format,
description, url, index. None of the speakers, photos, recordings, slug or
structured time this needs. `api-contract.md` §4 is the shape.

Two rules from the contract are implemented here rather than left to callers:

- **`status` is derived, not typed.** It is computed from `startAt` against now,
  unless a human set it explicitly — a cancelled session stays cancelled. A
  field someone has to remember to update goes stale within a month.
- **Photos and recordings are optional and often empty.** An in-person session
  with no photos yet, and an online one before its recording is published, are
  both normal states.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from app.models.common import ApiModel, Image, OrderedResource, Seo, Series, Url

SessionType = Literal["workshop", "talk", "webinar", "meetup", "bootcamp", "panel", "other"]
SessionFormat = Literal["in_person", "online", "hybrid"]
SessionStatus = Literal["upcoming", "completed", "cancelled"]
LinkKind = Literal["registration", "announcement", "repo", "resource", "recap"]
RecordingPlatform = Literal["youtube", "linkedin", "other"]


class Location(ApiModel):
    venue: str | None = None
    city: str | None = None
    country: str | None = None
    map_url: Url | None = None


class HostEvent(ApiModel):
    name: str
    organizer: str | None = None
    organizer_url: Url | None = None


class Speaker(ApiModel):
    name: str
    role: str | None = None
    profile_url: Url | None = None
    avatar_url: Url | None = None
    is_host: bool = False


class Photo(ApiModel):
    url: Url
    alt: str = ""
    caption: str | None = None
    credit: str | None = None
    width: int | None = None
    height: int | None = None
    order: int = 0


class Recording(ApiModel):
    platform: RecordingPlatform = "other"
    url: Url
    embed_url: Url | None = None
    duration_seconds: int | None = None
    language: str | None = None


class Slides(ApiModel):
    url: Url
    provider: str | None = None


class SessionLink(ApiModel):
    label: str
    url: Url
    kind: LinkKind = "resource"


class SessionBase(ApiModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=140)
    title: str
    summary: str = ""
    description: str = ""
    type: SessionType = "talk"
    format: SessionFormat = "in_person"
    start_at: datetime
    end_at: datetime | None = None
    timezone: str = "Asia/Colombo"
    status: SessionStatus | None = Field(
        default=None,
        description="Leave unset to derive from startAt. Set it to pin a value, e.g. cancelled.",
    )
    location: Location | None = None
    event: HostEvent | None = None
    speakers: list[Speaker] = Field(default_factory=list)
    cover: Image | None = None
    photos: list[Photo] = Field(default_factory=list)
    recordings: list[Recording] = Field(default_factory=list)
    slides: Slides | None = None
    links: list[SessionLink] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    series: Series | None = None
    audience_size: int | None = None
    featured: bool = False
    order: int = 0
    published: bool = True
    seo: Seo = Field(default_factory=Seo)
    meta: dict[str, object] = Field(default_factory=dict)


class SessionCreate(SessionBase):
    pass


class SessionUpdate(ApiModel):
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=140)
    title: str | None = None
    summary: str | None = None
    description: str | None = None
    type: SessionType | None = None
    format: SessionFormat | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = None
    status: SessionStatus | None = None
    location: Location | None = None
    event: HostEvent | None = None
    speakers: list[Speaker] | None = None
    cover: Image | None = None
    photos: list[Photo] | None = None
    recordings: list[Recording] | None = None
    slides: Slides | None = None
    links: list[SessionLink] | None = None
    tags: list[str] | None = None
    series: Series | None = None
    audience_size: int | None = None
    featured: bool | None = None
    order: int | None = None
    published: bool | None = None
    seo: Seo | None = None
    meta: dict[str, object] | None = None


class Session(OrderedResource):
    slug: str
    title: str
    summary: str = ""
    description: str = ""
    type: SessionType = "talk"
    format: SessionFormat = "in_person"
    start_at: datetime
    end_at: datetime | None = None
    timezone: str = "Asia/Colombo"
    status: SessionStatus
    location: Location | None = None
    event: HostEvent | None = None
    speakers: list[Speaker] = Field(default_factory=list)
    cover: Image | None = None
    photos: list[Photo] = Field(default_factory=list)
    recordings: list[Recording] = Field(default_factory=list)
    slides: Slides | None = None
    links: list[SessionLink] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    series: Series | None = None
    audience_size: int | None = None
    featured: bool = False
    seo: Seo = Field(default_factory=Seo)


def derive_status(
    start_at: datetime, end_at: datetime | None, stored: str | None, *, now: datetime | None = None
) -> SessionStatus:
    """Compute a session's status, respecting an explicit override.

    `cancelled` is never derived — someone set it, and time passing does not
    un-cancel a session. Everything else follows the clock.
    """
    if stored == "cancelled":
        return "cancelled"
    moment = now or datetime.now(UTC)
    finish = end_at or start_at
    if finish.tzinfo is None:
        finish = finish.replace(tzinfo=UTC)
    return "completed" if finish < moment else "upcoming"
