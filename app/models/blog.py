"""Blog posts — reshaped for a blog that now lives on the main website.

**The API stores metadata only.** Post bodies stay in Git and are fetched by
`dileepa-dev` at build time; see `content-pipeline.md`.

What changed from v1, and why:

- `link`, an absolute `https://blog.dileepa.dev/...`, becomes relative `path`
  plus a composed `canonicalUrl` — the host is moving, so consumers build it.
- `bannerUrl`, absolute and on the blog host, becomes `banner: { url, alt }` on
  Cloudinary — that host stops serving images.
- `date: str` becomes `publishedDate: datetime`, because strings do not sort.
- `excerpt` becomes `description`, matching the front-matter field name.

`draft` and `published` both exist and are not the same thing. `draft` is front
matter, written by the author in the blog repo. `published` is the platform-wide
visibility flag every resource carries, and **it alone gates what a public
caller sees**. `/blogs/sync` maps one to the other: `published = not draft`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.common import ApiModel, Image, OrderedResource, Seo, Series

#: The four reactions a reader can leave. Deliberately a closed set: an open
#: vocabulary turns the counter into free-text storage, and a reaction that only
#: one person can send is not a signal anyone can read.
ReactionKind = Literal["liked", "insightful", "useful", "learned"]

REACTION_KINDS: tuple[ReactionKind, ...] = ("liked", "insightful", "useful", "learned")


class ReactionCounts(ApiModel):
    """How many readers chose each reaction.

    Denormalised onto the post so rendering it is one read. `blog_reactions`
    remains the record of *who* chose what, and is what makes a reader able to
    change their mind without double-counting.
    """

    liked: int = 0
    insightful: int = 0
    useful: int = 0
    learned: int = 0


class BlogEngagement(ApiModel):
    """The mutable half of a post: counts, plus what this reader did.

    Separate from `BlogPost` because the post is built into a static page and
    these numbers are not. The page ships without them and asks for them at
    runtime, which is also why this is a small response rather than a whole
    post.
    """

    slug: str
    views: int = 0
    reactions: ReactionCounts = Field(default_factory=ReactionCounts)
    #: What this caller reacted with, if anything. Lets the UI show its own
    #: state as selected without a second request or a client-side guess.
    viewer_reaction: ReactionKind | None = None


class ReactionRequest(ApiModel):
    """Set, change, or clear this reader's reaction.

    `None` clears it. One request shape for all three because they are one
    operation from the reader's side — the button they press is a toggle, and
    the API should not make the client work out which verb that is.
    """

    reaction: ReactionKind | None = None


class BlogBase(ApiModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160)
    title: str
    description: str = ""
    path: str = Field(default="", description="Relative, e.g. /blog/{slug}. Never absolute.")
    published_date: datetime
    updated_date: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    series: Series | None = None
    banner: Image | None = None
    reading_time_minutes: int = 0
    draft: bool = False
    featured: bool = False
    order: int = 0
    source_path: str = ""
    content_hash: str = ""
    published: bool = True
    seo: Seo = Field(default_factory=Seo)
    meta: dict[str, object] = Field(default_factory=dict)


class BlogCreate(BlogBase):
    pass


class BlogUpdate(ApiModel):
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160)
    title: str | None = None
    description: str | None = None
    path: str | None = None
    published_date: datetime | None = None
    updated_date: datetime | None = None
    tags: list[str] | None = None
    series: Series | None = None
    banner: Image | None = None
    reading_time_minutes: int | None = None
    draft: bool | None = None
    featured: bool | None = None
    order: int | None = None
    source_path: str | None = None
    content_hash: str | None = None
    published: bool | None = None
    seo: Seo | None = None
    meta: dict[str, object] | None = None


class BlogSync(ApiModel):
    """The body the blog repo's workflow posts to `/blogs/sync`.

    `path` is relative and `banner.url` is a Cloudinary URL — the pipeline
    uploads through `POST /uploads` first. `published` is not accepted here:
    visibility follows `draft`, so the front matter stays the single place an
    author decides whether a post is live.
    """

    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=160)
    title: str
    description: str = ""
    path: str = ""
    published_date: datetime
    updated_date: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    series: Series | None = None
    banner: Image | None = None
    reading_time_minutes: int = 0
    draft: bool = False
    featured: bool = False
    order: int = 0
    source_path: str = ""
    content_hash: str = ""
    seo: Seo = Field(default_factory=Seo)
    meta: dict[str, object] = Field(default_factory=dict)


class BlogPost(OrderedResource):
    slug: str
    title: str
    description: str = ""
    path: str = ""
    canonical_url: str = ""
    published_date: datetime | None = None
    updated_date: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    series: Series | None = None
    banner: Image | None = None
    reading_time_minutes: int = 0
    draft: bool = False
    featured: bool = False
    source_path: str = ""
    content_hash: str = ""
    seo: Seo = Field(default_factory=Seo)
    #: Engagement counters. Present on the read model only — deliberately absent
    #: from `BlogCreate`, `BlogUpdate` and `BlogSync`, so neither an admin edit
    #: nor a pipeline re-run can overwrite a number it does not own. `/blogs/sync`
    #: writes with `$set` over the fields it sends, and these are not among them.
    views: int = 0
    reactions: ReactionCounts = Field(default_factory=ReactionCounts)
    #: Published comments, replies included. Denormalised so the blog index can
    #: show "12 comments" without reading every thread — the whole point of the
    #: field. Maintained with `$inc` on the four paths that can change it
    #: (public post, owner reply, publish/unpublish, delete), never recomputed
    #: on read. `scripts/reconcile_comment_counts.py` repairs drift.
    comment_count: int = 0


def blog_path(slug: str) -> str:
    return f"/blog/{slug}"


def canonical_url(site_url: str, path: str) -> str:
    return f"{site_url.rstrip('/')}{path}"
