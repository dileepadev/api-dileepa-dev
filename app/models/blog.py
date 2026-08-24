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

from pydantic import Field

from app.models.common import ApiModel, Image, OrderedResource, Seo, Series


class BlogLegacy(ApiModel):
    """The v1 values, kept for one release so the URL rewrite is reversible."""

    link: str | None = None
    banner_url: str | None = None
    date: str | None = None
    excerpt: str | None = None


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
    legacy: BlogLegacy | None = None


def blog_path(slug: str) -> str:
    return f"/blog/{slug}"


def canonical_url(site_url: str, path: str) -> str:
    return f"{site_url.rstrip('/')}{path}"
