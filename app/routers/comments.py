"""Blog comments — a public door and an admin one.

**Comments are visible the moment they are posted.** There is no approval
queue, so every defence is at the door: a hard rate limit, length bounds
enforced by the model, a depth cap, and a honeypot. What gets past them is
removed afterwards from the admin.

Two routers, because the two audiences are not the same:

- `public_router` hangs off `/blogs/{slug}/comments` and returns `PublicComment`,
  which has no field for an email address and therefore cannot leak one.
- `admin_router` is `/comments`, requires a token on **every** route including
  the list, and returns `Comment`, which does carry the email.

The admin routes are written out rather than built with `crud_router`. That
helper's list route is deliberately public — it is what serves `/projects` and
`/events` to the website — and a comment list is the one collection here where
public read access would disclose something a reader gave in confidence.
"""

from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.deps import CurrentUser, repository
from app.core.errors import NotFoundError
from app.core.pagination import ListParamsDep, Page, page
from app.core.rate_limit import limiter
from app.models.blog import ReactionRequest
from app.models.comment import (
    Comment,
    CommentAdminCreate,
    CommentCreate,
    CommentPosted,
    CommentThread,
    CommentUpdate,
    PublicComment,
    thread,
)
from app.repositories.base import Document, DocumentRepository, Filters, Sort
from app.services.reactions import apply_reaction

CommentsRepo = Annotated[DocumentRepository, Depends(repository("comments"))]
CommentReactionsRepo = Annotated[DocumentRepository, Depends(repository("comment_reactions"))]
BlogsRepo = Annotated[DocumentRepository, Depends(repository("blogs"))]

# Oldest first. A comment thread is a conversation and reads top to bottom;
# newest-first is for lists you scan, not for something you follow.
COMMENT_SORT: Sort = [("createdAt", 1)]

public_router = APIRouter(prefix="/blogs", tags=["comments"])
admin_router = APIRouter(prefix="/comments", tags=["comments"])


def commenter_key(request: Request, secret: str) -> str:
    """The same construction the reactions use, minus the slug.

    Not per-post here: recognising the same person across posts is the point of
    it on the moderation screen. Still a salted hash — enough to group, not
    enough to reverse into an address.
    """
    address = get_remote_address(request) or "unknown"
    return hashlib.sha256(f"{secret}:comment:{address}".encode()).hexdigest()


async def _post_or_404(slug: str, blogs: DocumentRepository) -> Document:
    document = await blogs.find_one({"slug": slug, "published": {"$ne": False}})
    if document is None:
        raise NotFoundError("Blog post not found.")
    return document


async def _visible(
    slug: str,
    repo: DocumentRepository,
    reactions: DocumentRepository,
    key: str,
) -> list[PublicComment]:
    """The visible comments on a post, each carrying this caller's own reaction.

    The reader's reactions are fetched in **one** query across the whole thread
    rather than one per comment. A thread of forty comments is forty round trips
    the other way, on the hottest read the blog has.
    """
    documents, _ = await repo.list(
        filters={"slug": slug, "published": {"$ne": False}},
        sort=COMMENT_SORT,
        limit=500,
        offset=0,
    )
    comments = [PublicComment.model_validate(doc) for doc in documents]
    if not comments:
        return comments

    mine, _ = await reactions.list(
        filters={"commentId": {"$in": [c.id for c in comments]}, "key": key},
        sort=None,
        limit=len(comments),
        offset=0,
    )
    chosen = {str(row.get("commentId")): row.get("reaction") for row in mine}
    for comment in comments:
        comment.viewer_reaction = chosen.get(comment.id)
    return comments


@public_router.get(
    "/{slug}/comments",
    response_model=list[CommentThread],
    summary="Read the comments on a post",
)
async def list_comments(
    slug: str,
    request: Request,
    repo: CommentsRepo,
    blogs: BlogsRepo,
    reactions: CommentReactionsRepo,
) -> list[CommentThread]:
    """Top-level comments, each with its replies. Oldest first."""
    await _post_or_404(slug, blogs)
    key = commenter_key(request, get_settings().jwt_secret)
    return thread(await _visible(slug, repo, reactions, key))


@public_router.post(
    "/{slug}/comments",
    response_model=CommentPosted,
    status_code=status.HTTP_201_CREATED,
    summary="Post a comment",
)
@limiter.limit(get_settings().rate_limit_comment)
async def post_comment(
    slug: str,
    payload: CommentCreate,
    request: Request,
    response: Response,
    repo: CommentsRepo,
    blogs: BlogsRepo,
) -> CommentPosted:
    """Accept a comment and show it immediately.

    `request` and `response` are unused by the body but required by slowapi,
    which reads the caller's address off one and writes the rate-limit headers
    onto the other.

    **A honeypot hit returns 201 and stores nothing.** Telling a bot that it
    was detected is how it learns which field gave it away; a success it cannot
    distinguish from the real thing is worth more than an honest 400. `accepted`
    is `False` so a *human* client could tell, but the UI does not look at it —
    there is no legitimate way for a person to trip this.
    """
    await _post_or_404(slug, blogs)

    if payload.honeypot.strip():
        return CommentPosted(accepted=False, comment=None)

    settings = get_settings()

    # Depth is capped at one. A reply to a reply is re-parented to the thread it
    # belongs to rather than rejected: the reader did nothing wrong, and the
    # comment still belongs under that conversation.
    parent_id: str | None = None
    if payload.parent_id:
        parent = await repo.get(payload.parent_id)
        if parent is not None and str(parent.get("slug")) == slug:
            parent_id = str(parent.get("parentId") or parent.get("_id"))

    document = await repo.create(
        {
            "slug": slug,
            "author": payload.author.strip(),
            "email": (payload.email or "").strip() or None,
            "body": payload.body.strip(),
            "parentId": parent_id,
            "authorIsOwner": False,
            "published": True,
            "key": commenter_key(request, settings.jwt_secret),
        }
    )
    return CommentPosted(accepted=True, comment=PublicComment.model_validate(document))


@admin_router.get("", response_model=Page[Comment], summary="List comments")
async def list_all_comments(
    params: ListParamsDep,
    user: CurrentUser,
    repo: CommentsRepo,
    slug: Annotated[str | None, Query()] = None,
    published: Annotated[bool | None, Query()] = None,
) -> Page[Comment]:
    """Every comment, hidden ones included. **Authenticated only.**

    Newest first here, unlike the public thread: this is a queue to work
    through, and the thing most likely to need attention is the newest.
    """
    filters: Filters = {}
    if slug is not None:
        filters["slug"] = slug
    if published is not None:
        filters["published"] = published

    documents, total = await repo.list(
        filters=filters,
        sort=[("createdAt", -1)],
        limit=params.limit,
        offset=params.offset,
    )
    return page([Comment.model_validate(doc) for doc in documents], total, params)


@public_router.post(
    "/{slug}/comments/{comment_id}/reactions",
    response_model=PublicComment,
    summary="React to a comment",
)
async def react_to_comment(
    slug: str,
    comment_id: str,
    payload: ReactionRequest,
    request: Request,
    repo: CommentsRepo,
    blogs: BlogsRepo,
    reactions: CommentReactionsRepo,
) -> PublicComment:
    """One reaction per reader per comment, changeable and clearable.

    Same four reactions as a post and the same toggle rule, applied by the same
    service — see `app/services/reactions.py`. Replies are comments, so this
    works on them without a second route.

    The slug is in the path and checked against the comment. It is not
    redundant: it keeps a comment id from being reacted to through a post it
    does not belong to, and it means an unpublished post's thread is unreachable
    here for the same reason it is unreachable everywhere else.
    """
    await _post_or_404(slug, blogs)

    comment = await repo.get(comment_id)
    if comment is None or str(comment.get("slug")) != slug:
        raise NotFoundError("Comment not found.")
    if comment.get("published") is False:
        raise NotFoundError("Comment not found.")

    key = commenter_key(request, get_settings().jwt_secret)
    updated, chosen = await apply_reaction(
        subjects=repo,
        subject_filter={"_id": comment["_id"]},
        records=reactions,
        record_filter={"commentId": comment_id, "key": key},
        record_seed={"commentId": comment_id, "key": key},
        requested=payload.reaction,
    )

    result = PublicComment.model_validate(updated or comment)
    result.viewer_reaction = chosen
    return result


@admin_router.post(
    "",
    response_model=Comment,
    status_code=status.HTTP_201_CREATED,
    summary="Reply as the author",
)
async def create_comment(
    payload: CommentAdminCreate,
    user: CurrentUser,
    repo: CommentsRepo,
    blogs: BlogsRepo,
) -> Comment:
    """The owner's own reply, marked as theirs.

    This is the **only** path that sets `authorIsOwner`. A reader cannot claim
    the badge because `CommentCreate` has no field for it and extra fields are
    forbidden — the distinction is enforced by the shape of the request, not by
    a check that could be forgotten.

    Not rate limited: it requires a token, and the owner is not the threat model.
    """
    await _post_or_404(payload.slug, blogs)

    parent_id: str | None = None
    if payload.parent_id:
        parent = await repo.get(payload.parent_id)
        if parent is not None and str(parent.get("slug")) == payload.slug:
            parent_id = str(parent.get("parentId") or parent.get("_id"))

    document = await repo.create(
        {
            "slug": payload.slug,
            "author": payload.author.strip(),
            "email": None,
            "body": payload.body.strip(),
            "parentId": parent_id,
            "authorIsOwner": True,
            "published": payload.published,
            "key": "",
        }
    )
    return Comment.model_validate(document)


@admin_router.patch("/{comment_id}", response_model=Comment, summary="Edit or hide a comment")
async def update_comment(
    comment_id: str,
    payload: CommentUpdate,
    user: CurrentUser,
    repo: CommentsRepo,
) -> Comment:
    """Hiding sets `published: False`; the row stays.

    Deletion is a separate, deliberate act. Hiding is reversible and keeps the
    replies underneath it addressable — `thread()` promotes orphaned replies to
    top level rather than losing them.
    """
    changes = payload.model_dump(by_alias=True, exclude_none=True)
    document = await repo.update(comment_id, changes) if changes else await repo.get(comment_id)
    if document is None:
        raise NotFoundError("Comment not found.")
    return Comment.model_validate(document)


@admin_router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
)
async def delete_comment(comment_id: str, user: CurrentUser, repo: CommentsRepo) -> None:
    """Permanent. Prefer hiding unless the content actually has to go."""
    if await repo.delete(comment_id) is None:
        raise NotFoundError("Comment not found.")
