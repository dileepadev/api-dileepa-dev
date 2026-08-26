"""Blog comments.

Comments are **visible as soon as they are posted**. There is no approval
queue, which is a deliberate trade: a conversation that waits on a moderator is
not a conversation. The cost is that spam reaches readers until it is removed,
and the defences are therefore all at the door — a hard rate limit, length
bounds, and a honeypot — rather than in a queue behind it.

Two shapes, and the difference between them is the point:

- `Comment` is what an admin reads. It carries the author's email and the
  hashed key that identifies a repeat commenter.
- `PublicComment` is what a reader reads. It carries neither.

They are separate classes rather than one class with a flag because a field
that is sometimes secret is a field that will eventually be returned by
accident. The public endpoint cannot serialise an email it has no field for.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.blog import ReactionCounts, ReactionKind
from app.models.common import ApiModel, TimestampedResource

#: Long enough for a real reply, short enough that the page stays readable and
#: a single request cannot carry an essay of spam.
BODY_MAX = 4000
AUTHOR_MAX = 80


class CommentCreate(ApiModel):
    """What a reader submits.

    `slug` is not here: it comes from the path, so a comment cannot be aimed at
    a different post than the one it was posted on.
    """

    author: str = Field(min_length=1, max_length=AUTHOR_MAX)
    #: Optional and never shown. Kept so a conversation can be followed up
    #: privately, and so a repeat commenter is recognisable to a human reading
    #: the moderation screen.
    email: str | None = Field(default=None, max_length=254)
    body: str = Field(min_length=1, max_length=BODY_MAX)
    #: The comment being replied to. Depth is capped at one: a reply to a reply
    #: is re-parented to the top-level comment, so the thread cannot grow a
    #: third level that the layout has no room for.
    parent_id: str | None = None
    #: A field no human ever fills in, because no human can see it. Anything
    #: arriving with it set is a bot that filled in every input it found, and is
    #: accepted-then-discarded rather than rejected — telling a bot it failed is
    #: how it learns to stop failing.
    honeypot: str = ""


class CommentAdminCreate(ApiModel):
    """A comment written from the admin — the owner replying in their own thread.

    Separate from `CommentCreate` because the two differ in every way that
    matters: this one names its own post, sets no honeypot, is not rate limited,
    and is marked as the author's. It is the only path that sets
    `authorIsOwner`, which is why a reader cannot forge that badge — there is no
    field for it on the public model.
    """

    slug: str
    author: str = Field(min_length=1, max_length=AUTHOR_MAX)
    body: str = Field(min_length=1, max_length=BODY_MAX)
    parent_id: str | None = None
    published: bool = True


class CommentUpdate(ApiModel):
    """Admin edits. A reader cannot reach this."""

    author: str | None = Field(default=None, max_length=AUTHOR_MAX)
    body: str | None = Field(default=None, max_length=BODY_MAX)
    published: bool | None = None


class PublicComment(TimestampedResource):
    """What a reader sees. No email, no visitor key, by construction."""

    slug: str
    author: str
    body: str
    parent_id: str | None = None
    #: Marks the site owner's own replies, so an answer from the author is
    #: distinguishable from an answer by a passer-by.
    author_is_owner: bool = False
    #: The same four reactions posts carry. One vocabulary across the site means
    #: one enum in the API and one picker in the UI.
    reactions: ReactionCounts = Field(default_factory=ReactionCounts)
    #: What *this* caller reacted with. Filled in per request, not stored on the
    #: comment — the stored document has counts, not opinions.
    viewer_reaction: ReactionKind | None = None


class Comment(TimestampedResource):
    """What an admin sees: everything stored."""

    slug: str
    author: str
    email: str | None = None
    body: str
    parent_id: str | None = None
    author_is_owner: bool = False
    reactions: ReactionCounts = Field(default_factory=ReactionCounts)
    published: bool = True
    #: The same salted hash the reactions and views use. Recognises a repeat
    #: commenter without storing an address.
    key: str = ""


class CommentThread(ApiModel):
    """A top-level comment and its replies, oldest first within the thread."""

    comment: PublicComment
    replies: list[PublicComment] = Field(default_factory=list)


class CommentPosted(ApiModel):
    """The answer to a successful post.

    Returns the comment so the client can render it without refetching the
    whole thread — and `accepted: False` for a submission that was silently
    dropped, which the UI still reports as success.
    """

    accepted: bool = True
    comment: PublicComment | None = None


def thread(comments: list[PublicComment]) -> list[CommentThread]:
    """Group a flat list into one level of threads.

    Replies whose parent is missing — deleted, or hidden by an admin — become
    top-level rather than disappearing with it. Losing a reply because someone
    removed the comment above it destroys a conversation the reply may still
    make sense in.
    """
    tops = [c for c in comments if not c.parent_id]
    by_id = {c.id: c for c in tops}
    threads = {c.id: CommentThread(comment=c) for c in tops}

    orphans: list[PublicComment] = []
    for comment in comments:
        if not comment.parent_id:
            continue
        if comment.parent_id in threads:
            threads[comment.parent_id].replies.append(comment)
        else:
            orphans.append(comment)

    ordered = [threads[c.id] for c in tops if c.id in by_id]
    ordered.extend(CommentThread(comment=orphan) for orphan in orphans)
    ordered.sort(key=_sort_key)
    for item in ordered:
        item.replies.sort(key=lambda reply: reply.created_at or datetime.min)
    return ordered


def _sort_key(item: CommentThread) -> datetime:
    return item.comment.created_at or datetime.min
