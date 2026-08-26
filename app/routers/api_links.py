"""The API's endpoint catalogue — `GET /api-links`.

What it is for: the admin dashboard shows, on every screen, the endpoint that
screen reads and writes and the variables it expects. Answering that used to
mean opening two repositories side by side.

Two things about it worth knowing.

**It is admin-only.** Nothing on the public website reads it, and it is not a
public description of the API — that is the reference at `/docs`. Requiring a
token is what keeps it out of the website by construction rather than by
convention.

**It is derived, never written.** `app.core.routes.catalogue` reads the live
route table, so the catalogue and the routes cannot disagree. A hand-maintained
list would be a second contract, and the second one is always the stale one.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.deps import AdminUser
from app.core.pagination import ListParamsDep, Page, page
from app.core.routes import catalogue
from app.models.api_links import ApiLink

router = APIRouter(prefix="/api-links", tags=["api-links"])


@router.get("", response_model=Page[ApiLink], summary="List the API's endpoints")
async def list_api_links(
    request: Request,
    params: ListParamsDep,
    _: AdminUser,
) -> Page[ApiLink]:
    """Every endpoint this API serves, grouped by tag.

    URLs are absolute against the host this request arrived on, so a catalogue
    read from localhost points at localhost and one read from production points
    at production — there is no base URL to configure and none to get wrong.
    """
    settings = get_settings()
    base_url = str(request.base_url).rstrip("/")
    docs_url = f"{base_url}{settings.docs_path}" if settings.serve_docs else None

    links = catalogue(request.app, base_url=base_url, docs_url=docs_url)
    window = links[params.offset : params.offset + params.limit]
    return page(window, len(links), params)
