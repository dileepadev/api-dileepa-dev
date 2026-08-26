"""About — a singleton.

One document, no list endpoint, no ordering. The v1 shape is kept exactly:
`GET /about`, `POST /about`, `PATCH /about`, `DELETE /about`, none of them
taking an id.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import AdminUser, repository
from app.core.errors import ConflictError, NotFoundError
from app.models.common import DeleteResult
from app.models.profile import About, AboutCreate, AboutUpdate
from app.repositories.base import DocumentRepository

router = APIRouter(prefix="/about", tags=["about"])

AboutRepo = Annotated[DocumentRepository, Depends(repository("about"))]

_NOT_FOUND = "There is no about record yet. Create one with POST /about."


@router.get("", response_model=About, summary="Get the about record")
async def read_about(repo: AboutRepo) -> About:
    document = await repo.find_one({})
    if document is None:
        raise NotFoundError(_NOT_FOUND)
    return About.model_validate(document)


@router.post(
    "",
    response_model=About,
    status_code=status.HTTP_201_CREATED,
    summary="Create the about record",
)
async def create_about(payload: AboutCreate, _: AdminUser, repo: AboutRepo) -> About:
    """Create the singleton. Fails if one already exists — update it instead."""
    if await repo.find_one({}) is not None:
        raise ConflictError("An about record already exists. Update it with PATCH /about.")
    document = await repo.create(payload.model_dump(by_alias=True))
    return About.model_validate(document)


@router.patch("", response_model=About, summary="Update the about record")
async def update_about(payload: AboutUpdate, _: AdminUser, repo: AboutRepo) -> About:
    existing = await repo.find_one({})
    if existing is None:
        raise NotFoundError(_NOT_FOUND)
    changes = payload.model_dump(by_alias=True, exclude_unset=True)
    if not changes:
        return About.model_validate(existing)
    updated = await repo.update(str(existing["_id"]), changes)
    if updated is None:  # pragma: no cover - found a line ago
        raise NotFoundError(_NOT_FOUND)
    return About.model_validate(updated)


@router.delete("", response_model=DeleteResult, summary="Delete the about record")
async def delete_about(_: AdminUser, repo: AboutRepo) -> DeleteResult:
    existing = await repo.find_one({})
    if existing is None:
        raise NotFoundError(_NOT_FOUND)
    await repo.delete(str(existing["_id"]))
    return DeleteResult(id=str(existing["_id"]))
