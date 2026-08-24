"""Blogs.

The API stores metadata only; post bodies stay in Git and are fetched by the
main site at build time.

`POST /blogs/sync` is the blog repo's pipeline, guarded by the same `x-api-key`
header and the same environment variable as v1, so the workflow needs no change
at cutover. What did change is the body: `path` is relative, the banner is a
Cloudinary URL, and `published` is derived from the front matter's `draft`
rather than sent.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, status

from app.core.config import get_settings
from app.core.deps import OptionalUser, SettingsDep, repository, require_api_key
from app.core.pagination import ListParamsDep, Page, page
from app.models.blog import BlogCreate, BlogPost, BlogSync, BlogUpdate, blog_path, canonical_url
from app.repositories.base import Document, DocumentRepository, Filters, Sort
from app.routers.crud import crud_router, visibility_filter

# Newest post first. `publishedDate` is a real datetime in v2.0.0, so this sorts
# correctly — v1 sorted a free-text `date` string and did not.
BLOG_SORT: Sort = [("featured", -1), ("publishedDate", -1), ("order", -1)]


def with_canonical(document: Document, site_url: str | None = None) -> Document:
    """Compose `path` and `canonicalUrl` from the slug when they are missing.

    A row the URL migration has not touched yet still carries only the old
    absolute `link`. Composing here means the API is correct before the
    migration runs, and unchanged after it.
    """
    site_url = site_url or get_settings().site_url
    slug = str(document.get("slug", ""))
    path = str(document.get("path") or (blog_path(slug) if slug else ""))
    canonical = document.get("canonicalUrl") or (canonical_url(site_url, path) if path else "")
    return {**document, "path": path, "canonicalUrl": canonical}


router = crud_router(
    collection="blogs",
    prefix="/blogs",
    tag="blogs",
    label="blog post",
    read_model=BlogPost,
    create_model=BlogCreate,
    update_model=BlogUpdate,
    sort=BLOG_SORT,
    slug_field="slug",
    include_list=False,
    transform=with_canonical,
)

BlogsRepo = Annotated[DocumentRepository, Depends(repository("blogs"))]


@router.get("", response_model=Page[BlogPost], summary="List blog posts")
async def list_blogs(
    params: ListParamsDep,
    user: OptionalUser,
    repo: BlogsRepo,
    settings: SettingsDep,
    tag: Annotated[str | None, Query()] = None,
    series: Annotated[str | None, Query()] = None,
    featured: Annotated[bool | None, Query()] = None,
    published: Annotated[bool | None, Query()] = None,
) -> Page[BlogPost]:
    """List posts, newest first."""
    filters: Filters = dict(visibility_filter(user, published))
    if tag is not None:
        filters["tags"] = tag
    if series is not None:
        filters["series.name"] = series
    if featured is not None:
        filters["featured"] = featured

    documents, total = await repo.list(
        filters=filters, sort=BLOG_SORT, limit=params.limit, offset=params.offset
    )
    items = [BlogPost.model_validate(with_canonical(doc, settings.site_url)) for doc in documents]
    return page(items, total, params)


@router.post(
    "/sync",
    response_model=BlogPost,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_api_key)],
    summary="Upsert a post from the blog repo's pipeline",
)
async def sync_blog(payload: BlogSync, repo: BlogsRepo, settings: SettingsDep) -> BlogPost:
    """Create or update a post by slug. Idempotent, so a re-run is harmless.

    `published` is not accepted in the body: visibility follows `draft`, which
    keeps the front matter the single place an author decides whether a post is
    live.
    """
    data = payload.model_dump(by_alias=True)
    path = data.get("path") or blog_path(payload.slug)
    data["path"] = path
    data["canonicalUrl"] = canonical_url(settings.site_url, path)
    data["published"] = not payload.draft

    document = await repo.upsert_by("slug", payload.slug, data)
    return BlogPost.model_validate(with_canonical(document, settings.site_url))
