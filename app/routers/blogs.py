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

import hashlib
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Query, Request, status
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.deps import OptionalUser, SettingsDep, repository, require_api_key
from app.core.errors import ConflictError, NotFoundError
from app.core.pagination import ListParamsDep, Page, page
from app.models.blog import (
    BlogCreate,
    BlogEngagement,
    BlogPost,
    BlogSync,
    BlogUpdate,
    ReactionCounts,
    ReactionRequest,
    blog_path,
    canonical_url,
)
from app.repositories.base import Document, DocumentRepository, Filters, Sort, utc_now
from app.routers.crud import crud_router, visibility_filter
from app.services.reactions import apply_reaction

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


# --- Engagement ------------------------------------------------------------
#
# Views and reactions are the one part of a post that changes after it is
# published. The pages themselves are static — built once, from Git and this
# API — so these numbers cannot be baked in. They live behind three small
# endpoints the page calls at runtime.
#
# Neither counter identifies a reader. Both are keyed on a salted hash of the
# caller's address and the slug, which is enough to recognise a repeat and not
# enough to reconstruct who it was. The hash is salted with `JWT_SECRET`, so the
# keys are not reversible with a rainbow table over an address space that small.

BlogViewsRepo = Annotated[DocumentRepository, Depends(repository("blog_views"))]
BlogReactionsRepo = Annotated[DocumentRepository, Depends(repository("blog_reactions"))]

#: How long one address counts as the same reader for view purposes.
VIEW_WINDOW = timedelta(hours=24)


def visitor_key(request: Request, slug: str, secret: str) -> str:
    """An opaque, per-post, per-reader key.

    The slug is inside the hash rather than beside it so a key from one post
    cannot be replayed against another, and the address is never stored in any
    form that can be read back.
    """
    address = get_remote_address(request) or "unknown"
    digest = hashlib.sha256(f"{secret}:{slug}:{address}".encode())
    return digest.hexdigest()


def _counts(document: Document | None) -> ReactionCounts:
    raw = (document or {}).get("reactions")
    return ReactionCounts.model_validate(raw if isinstance(raw, dict) else {})


async def _engagement(
    slug: str,
    post: Document,
    reactions_repo: DocumentRepository,
    key: str,
) -> BlogEngagement:
    existing = await reactions_repo.find_one({"slug": slug, "key": key})
    return BlogEngagement(
        slug=slug,
        views=int(post.get("views") or 0),
        reactions=_counts(post),
        viewer_reaction=(existing or {}).get("reaction"),
    )


async def _published_post(slug: str, repo: DocumentRepository) -> Document:
    """Look up a post that a public caller is allowed to engage with.

    Unpublished and draft posts are a 404 here rather than a 403: engagement is
    a public surface, and confirming that a slug exists but is hidden leaks the
    thing being hidden.
    """
    document = await repo.find_one({"slug": slug, "published": {"$ne": False}})
    if document is None:
        raise NotFoundError("Blog post not found.")
    return document


@router.get(
    "/{slug}/engagement",
    response_model=BlogEngagement,
    summary="Read view and reaction counts for a post",
)
async def get_engagement(
    slug: str,
    request: Request,
    repo: BlogsRepo,
    reactions_repo: BlogReactionsRepo,
    settings: SettingsDep,
) -> BlogEngagement:
    """Counts, plus whatever this caller already reacted with.

    Read-only and safe to call on every page load, which is what the static
    post page does to fill in the numbers it could not build in.
    """
    post = await _published_post(slug, repo)
    key = visitor_key(request, slug, settings.jwt_secret)
    return await _engagement(slug, post, reactions_repo, key)


@router.post(
    "/{slug}/views",
    response_model=BlogEngagement,
    summary="Record a view of a post",
)
async def record_view(
    slug: str,
    request: Request,
    repo: BlogsRepo,
    views_repo: BlogViewsRepo,
    reactions_repo: BlogReactionsRepo,
    settings: SettingsDep,
) -> BlogEngagement:
    """Count a view once per reader per 24 hours.

    The de-duplication is the unique index, not a check in this handler. A
    read-then-write would let two concurrent requests both conclude they are the
    first; here the second `create` raises `ConflictError` and the increment
    simply does not happen.

    A duplicate is not an error from the caller's side — they asked for the post
    to be counted and it already is — so it returns the current numbers with the
    same 200 as a first view. A client that reloads gets a truthful count rather
    than an exception to handle.
    """
    post = await _published_post(slug, repo)
    key = visitor_key(request, slug, settings.jwt_secret)

    try:
        await views_repo.create({"key": key, "slug": slug, "expiresAt": utc_now() + VIEW_WINDOW})
    except ConflictError:
        # Seen already inside the window. Report, do not increment.
        return await _engagement(slug, post, reactions_repo, key)

    updated = await repo.increment({"slug": slug}, {"views": 1})
    return await _engagement(slug, updated or post, reactions_repo, key)


@router.post(
    "/{slug}/reactions",
    response_model=BlogEngagement,
    summary="Set, change, or clear this reader's reaction",
)
async def set_reaction(
    slug: str,
    payload: ReactionRequest,
    request: Request,
    repo: BlogsRepo,
    reactions_repo: BlogReactionsRepo,
    settings: SettingsDep,
) -> BlogEngagement:
    """One reaction per reader per post.

    Sending a different reaction moves the reader's vote; sending `null`, or the
    one they already chose, clears it. The aggregate on the post is adjusted by
    the delta between the old choice and the new one, so the counts stay
    consistent without recounting the reactions collection on every write.
    """
    post = await _published_post(slug, repo)
    key = visitor_key(request, slug, settings.jwt_secret)

    updated, _chosen = await apply_reaction(
        subjects=repo,
        subject_filter={"slug": slug},
        records=reactions_repo,
        record_filter={"slug": slug, "key": key},
        record_seed={"slug": slug, "key": key},
        requested=payload.reaction,
    )
    return await _engagement(slug, updated or post, reactions_repo, key)
