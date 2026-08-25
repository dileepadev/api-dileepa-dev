"""Events — reshaped in v2.0.0.

The v1 `events` collection carried seven fields: title, date (string),
location, format, description, url, index. None of the speakers, photos,
recordings, slug or structured time this needs. `api-contract.md` §4 is the
shape.

Two rules from the contract are implemented here rather than left to callers:

- **`status` is derived, not typed.** It is computed from `startAt` against now,
  unless a human set it explicitly — a cancelled event stays cancelled. A
  field someone has to remember to update goes stale within a month.
- **Photos and recordings are optional and often empty.** An in-person event
  with no photos yet, and an online one before its recording is published, are
  both normal states.

`Host` is the umbrella an event was delivered under — a conference, a meetup
series, a company's developer programme. The event is the thing that happened;
the host is who put it on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from app.models.common import ApiModel, Image, OrderedResource, Seo, Series, Url

EventType = Literal["workshop", "talk", "webinar", "meetup", "bootcamp", "panel", "other"]
EventFormat = Literal["in_person", "online", "hybrid"]
EventStatus = Literal["upcoming", "completed", "cancelled"]
LinkKind = Literal["registration", "announcement", "repo", "resource", "recap"]
RecordingPlatform = Literal["youtube", "linkedin", "other"]


class Location(ApiModel):
    venue: str | None = None
    city: str | None = None
    country: str | None = None
    map_url: Url | None = None


class Host(ApiModel):
    """The conference, meetup series or programme the event ran under."""

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


class EventLink(ApiModel):
    label: str
    url: Url
    kind: LinkKind = "resource"


class EventBase(ApiModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=140)
    title: str
    summary: str = ""
    description: str = ""
    type: EventType = "talk"
    format: EventFormat = "in_person"
    start_at: datetime
    end_at: datetime | None = None
    timezone: str = "Asia/Colombo"
    status: EventStatus | None = Field(
        default=None,
        description="Leave unset to derive from startAt. Set it to pin a value, e.g. cancelled.",
    )
    location: Location | None = None
    host: Host | None = None
    speakers: list[Speaker] = Field(default_factory=list)
    cover: Image | None = None
    photos: list[Photo] = Field(default_factory=list)
    recordings: list[Recording] = Field(default_factory=list)
    slides: Slides | None = None
    links: list[EventLink] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    series: Series | None = None
    audience_size: int | None = None
    featured: bool = False
    order: int = 0
    published: bool = True
    seo: Seo = Field(default_factory=Seo)
    meta: dict[str, object] = Field(default_factory=dict)


class EventCreate(EventBase):
    pass


class EventUpdate(ApiModel):
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=140)
    title: str | None = None
    summary: str | None = None
    description: str | None = None
    type: EventType | None = None
    format: EventFormat | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = None
    status: EventStatus | None = None
    location: Location | None = None
    host: Host | None = None
    speakers: list[Speaker] | None = None
    cover: Image | None = None
    photos: list[Photo] | None = None
    recordings: list[Recording] | None = None
    slides: Slides | None = None
    links: list[EventLink] | None = None
    tags: list[str] | None = None
    series: Series | None = None
    audience_size: int | None = None
    featured: bool | None = None
    order: int | None = None
    published: bool | None = None
    seo: Seo | None = None
    meta: dict[str, object] | None = None


class Event(OrderedResource):
    slug: str
    title: str
    summary: str = ""
    description: str = ""
    type: EventType = "talk"
    format: EventFormat = "in_person"
    start_at: datetime
    end_at: datetime | None = None
    timezone: str = "Asia/Colombo"
    status: EventStatus
    location: Location | None = None
    host: Host | None = None
    speakers: list[Speaker] = Field(default_factory=list)
    cover: Image | None = None
    photos: list[Photo] = Field(default_factory=list)
    recordings: list[Recording] = Field(default_factory=list)
    slides: Slides | None = None
    links: list[EventLink] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    series: Series | None = None
    audience_size: int | None = None
    featured: bool = False
    seo: Seo = Field(default_factory=Seo)


def derive_status(
    start_at: datetime, end_at: datetime | None, stored: str | None, *, now: datetime | None = None
) -> EventStatus:
    """Compute an event's status, respecting an explicit override.

    `cancelled` is never derived — someone set it, and time passing does not
    un-cancel an event. Everything else follows the clock.
    """
    if stored == "cancelled":
        return "cancelled"
    moment = now or datetime.now(UTC)
    finish = end_at or start_at
    if finish.tzinfo is None:
        finish = finish.replace(tzinfo=UTC)
    return "completed" if finish < moment else "upcoming"
