"""Sessions — net-new in v2.0.0, superseding `events`.

`status` is derived on read rather than stored, so a session that has happened
says so without anyone remembering to edit it. An explicit `cancelled` is
respected; time passing does not un-cancel a session.

Ordering follows the contract: upcoming sessions read soonest-first, completed
ones most-recent-first. Sorting one list by two opposite rules is not possible
in a single query, so the split is explicit — `?status=upcoming` sorts ascending
and everything else sorts descending.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, Query

from app.core.deps import OptionalUser, repository
from app.core.pagination import ListParamsDep, Page, page
from app.models.session import (
    Session,
    SessionCreate,
    SessionFormat,
    SessionStatus,
    SessionType,
    SessionUpdate,
    derive_status,
)
from app.repositories.base import Document, DocumentRepository, Filters, Sort
from app.routers.crud import crud_router, visibility_filter

SESSION_SORT_PAST: Sort = [("featured", -1), ("startAt", -1), ("order", -1)]
SESSION_SORT_UPCOMING: Sort = [("featured", -1), ("startAt", 1), ("order", -1)]


def with_status(document: Document, *, now: datetime | None = None) -> Document:
    """Fill in the derived `status` before the response model validates."""
    start_at = document.get("startAt")
    if not isinstance(start_at, datetime):
        # A session with no usable start time keeps whatever was stored; the
        # response model requires a status, so fall back to upcoming.
        return {**document, "status": document.get("status") or "upcoming"}
    end_at = document.get("endAt")
    return {
        **document,
        "status": derive_status(
            start_at,
            end_at if isinstance(end_at, datetime) else None,
            document.get("status"),
            now=now,
        ),
    }


router = crud_router(
    collection="sessions",
    prefix="/sessions",
    tag="sessions",
    label="session",
    read_model=Session,
    create_model=SessionCreate,
    update_model=SessionUpdate,
    sort=SESSION_SORT_PAST,
    slug_field="slug",
    include_list=False,
    transform=with_status,
)

SessionsRepo = Annotated[DocumentRepository, Depends(repository("sessions"))]


def _status_filter(wanted: SessionStatus, now: datetime) -> Filters:
    """Express a derived status as a query, so paging stays correct.

    Filtering in Python after the query would make `total` and `limit` lie.
    """
    if wanted == "cancelled":
        return {"status": "cancelled"}
    if wanted == "upcoming":
        return {"status": {"$ne": "cancelled"}, "startAt": {"$gte": now}}
    return {"status": {"$ne": "cancelled"}, "startAt": {"$lt": now}}


@router.get("", response_model=Page[Session], summary="List sessions")
async def list_sessions(
    params: ListParamsDep,
    user: OptionalUser,
    repo: SessionsRepo,
    status: Annotated[SessionStatus | None, Query()] = None,
    # `type` and `format` shadow builtins. They are the contract's parameter
    # names and appear in the OpenAPI spec, so they are not renamed here.
    type: Annotated[SessionType | None, Query()] = None,
    format: Annotated[SessionFormat | None, Query()] = None,
    year: Annotated[int | None, Query(ge=1970, le=2999)] = None,
    tag: Annotated[str | None, Query()] = None,
    featured: Annotated[bool | None, Query()] = None,
    published: Annotated[bool | None, Query()] = None,
) -> Page[Session]:
    """List sessions.

    Upcoming sessions sort soonest first; everything else sorts most recent
    first. Filters combine.
    """
    now = datetime.now(UTC)
    filters: Filters = dict(visibility_filter(user, published))
    if status is not None:
        filters.update(_status_filter(status, now))
    if type is not None:
        filters["type"] = type
    if format is not None:
        filters["format"] = format
    if tag is not None:
        filters["tags"] = tag
    if featured is not None:
        filters["featured"] = featured
    if year is not None:
        start = datetime(year, 1, 1, tzinfo=UTC)
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
        existing = filters.get("startAt")
        window: dict[str, Any] = {"$gte": start, "$lt": end}
        # A year filter and an upcoming filter both constrain startAt; keep the
        # tighter of the two bounds rather than letting one overwrite the other.
        if isinstance(existing, dict):
            if "$gte" in existing:
                window["$gte"] = max(existing["$gte"], start)
            if "$lt" in existing:
                window["$lt"] = min(existing["$lt"], end)
        filters["startAt"] = window

    sort = SESSION_SORT_UPCOMING if status == "upcoming" else SESSION_SORT_PAST
    documents, total = await repo.list(
        filters=filters, sort=sort, limit=params.limit, offset=params.offset
    )
    return page(
        [Session.model_validate(with_status(doc, now=now)) for doc in documents], total, params
    )
