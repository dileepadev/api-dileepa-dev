"""Projects — net-new in v2.0.0.

There is no `projects` module in v1, despite the admin README advertising one.
The shape follows `api-contract.md` §3.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.common import ApiModel, Image, Metric, OrderedResource, Period, Seo, Url

ProjectStatus = Literal["active", "maintained", "archived", "concept"]


class ProjectLinks(ApiModel):
    repo: Url | None = None
    demo: Url | None = None
    docs: Url | None = None
    case_study: Url | None = None
    package: Url | None = None


class GalleryItem(ApiModel):
    url: Url
    alt: str = ""
    caption: str | None = None
    order: int = 0


class ProjectBase(ApiModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    name: str
    tagline: str = ""
    description: str = ""
    status: ProjectStatus = "active"
    role: str | None = None
    period: Period | None = None
    stack: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    links: ProjectLinks = Field(default_factory=ProjectLinks)
    cover: Image | None = None
    gallery: list[GalleryItem] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    featured: bool = False
    order: int = 0
    published: bool = True
    seo: Seo = Field(default_factory=Seo)
    meta: dict[str, object] = Field(default_factory=dict)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ApiModel):
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    name: str | None = None
    tagline: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    role: str | None = None
    period: Period | None = None
    stack: list[str] | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None
    links: ProjectLinks | None = None
    cover: Image | None = None
    gallery: list[GalleryItem] | None = None
    highlights: list[str] | None = None
    metrics: list[Metric] | None = None
    featured: bool | None = None
    order: int | None = None
    published: bool | None = None
    seo: Seo | None = None
    meta: dict[str, object] | None = None


class Project(OrderedResource):
    slug: str
    name: str
    tagline: str = ""
    description: str = ""
    status: ProjectStatus = "active"
    role: str | None = None
    period: Period | None = None
    stack: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    links: ProjectLinks = Field(default_factory=ProjectLinks)
    cover: Image | None = None
    gallery: list[GalleryItem] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    featured: bool = False
    seo: Seo = Field(default_factory=Seo)
