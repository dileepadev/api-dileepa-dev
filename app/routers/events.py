"""`GET /events` — a deprecated alias over the sessions collection.

It returns sessions projected into the v1 shape (`title`, `date` as a string,
`location`, `format`, `description`, `url`, `index`) so the main site and admin
keep working mid-migration. It is read-only: v1's write paths are not carried
over, because everything that writes here is being retargeted at `/sessions` in
the same release.

**Remove this in v2.1.0, not before**, and only once no consumer calls it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.core.deprecation import mark_deprecated
from app.core.deps import OptionalUser, repository
from app.models.common import ApiModel
from app.repositories.base import Document, DocumentRepository
from app.routers.crud import visibility_filter
from app.routers.sessions import SESSION_SORT_PAST

router = APIRouter(prefix="/events", tags=["events"])

SessionsRepo = Annotated[DocumentRepository, Depends(repository("sessions"))]

# The v1 list cap. `/events` never paginated, and adding pagination to a
# deprecated alias would be a second shape for consumers to learn.
_MAX_EVENTS = 200

_FORMAT_LABELS = {"in_person": "In-Person", "online": "Online", "hybrid": "Hybrid"}


class LegacyEvent(ApiModel):
    """The v1 `EventDto`, unchanged."""

    title: str
    date: str
    location: str
    format: str
    description: str
    url: str
    index: int


def project_to_v1(document: Document) -> LegacyEvent:
    """Flatten a session into the seven fields v1 exposed."""
    start_at = document.get("startAt")
    date = start_at.date().isoformat() if isinstance(start_at, datetime) else str(start_at or "")

    location = document.get("location") or {}
    if isinstance(location, dict):
        parts = [location.get("venue"), location.get("city"), location.get("country")]
        location_label = ", ".join(part for part in parts if part)
    else:  # pragma: no cover - defensive against a hand-edited document
        location_label = str(location)
    if not location_label and document.get("format") == "online":
        location_label = "Online"

    url = ""
    links = document.get("links") or []
    if isinstance(links, list):
        # v1 had one URL. Registration is the closest equivalent, then whatever
        # link the session lists first.
        entries = [link for link in links if isinstance(link, dict)]
        registration = next((link for link in entries if link.get("kind") == "registration"), None)
        chosen = registration or (entries[0] if entries else None)
        url = str((chosen or {}).get("url", ""))

    return LegacyEvent(
        title=str(document.get("title", "")),
        date=date,
        location=location_label,
        format=_FORMAT_LABELS.get(str(document.get("format", "")), str(document.get("format", ""))),
        description=str(document.get("summary") or document.get("description") or ""),
        url=url,
        index=int(document.get("order", document.get("index", 0)) or 0),
    )


@router.get(
    "",
    response_model=list[LegacyEvent],
    summary="List events (deprecated — use /sessions)",
    deprecated=True,
)
async def list_events(
    response: Response,
    user: OptionalUser,
    repo: SessionsRepo,
) -> list[Any]:
    """Sessions in the v1 event shape. Returns a bare array, as v1 did."""
    mark_deprecated(response, "/sessions")
    documents, _ = await repo.list(
        filters=visibility_filter(user, None), sort=SESSION_SORT_PAST, limit=_MAX_EVENTS
    )
    return [project_to_v1(doc) for doc in documents]
