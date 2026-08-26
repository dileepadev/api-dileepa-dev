"""Projects — net-new in v2.0.0.

The CRUD half comes from the factory. This module adds the filters the contract
specifies, and the sort: featured first, then priority, then most recent.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query

from app.core.deps import OptionalUser, repository
from app.core.pagination import ListParamsDep, Page, page
from app.models.project import Project, ProjectCreate, ProjectStatus, ProjectUpdate
from app.repositories.base import DocumentRepository, Filters, Sort
from app.routers.crud import crud_router, visibility_filter

PROJECT_SORT: Sort = [("featured", -1), ("order", -1), ("period.start", -1), ("_id", -1)]

router = crud_router(
    collection="projects",
    prefix="/projects",
    tag="projects",
    label="project",
    read_model=Project,
    create_model=ProjectCreate,
    update_model=ProjectUpdate,
    sort=PROJECT_SORT,
    slug_field="slug",
    include_list=False,
)

ProjectsRepo = Annotated[DocumentRepository, Depends(repository("projects"))]


@router.get("", response_model=Page[Project], summary="List projects")
async def list_projects(
    params: ListParamsDep,
    user: OptionalUser,
    repo: ProjectsRepo,
    featured: Annotated[bool | None, Query()] = None,
    status: Annotated[ProjectStatus | None, Query()] = None,
    tag: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    published: Annotated[bool | None, Query()] = None,
) -> Page[Project]:
    """List projects, newest and most prominent first.

    Sorted by `featured`, then `order` (higher first), then the start of the
    project's period.
    """
    filters: Filters = dict(visibility_filter(user, published))
    if featured is not None:
        filters["featured"] = featured
    if status is not None:
        filters["status"] = status
    if tag is not None:
        filters["tags"] = tag
    if category is not None:
        filters["categories"] = category

    documents, total = await repo.list(
        filters=filters, sort=PROJECT_SORT, limit=params.limit, offset=params.offset
    )
    return page([Project.model_validate(doc) for doc in documents], total, params)
