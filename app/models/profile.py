"""The six resources ported straight from v1.

Field names and types match the existing documents exactly. The only additions
are the platform-wide fields from `OrderedResource`, all optional with defaults,
so these models read a v1 document without a migration having run first.

`about` is a singleton: one document, no `order`, no list endpoint.
"""

from __future__ import annotations

from pydantic import Field

from app.models.common import ApiModel, Logo, OrderedResource, TimestampedResource, Url


class AboutImages(ApiModel):
    banner_webp: Url = ""
    profile_png: Url = ""
    profile_webp: Url = ""


class AboutLinks(ApiModel):
    website: str = ""
    email: str = ""
    github: str = ""
    linkedin: str = ""
    xtwitter: str = ""
    instagram: str = ""
    youtube: str = ""
    facebook: str | None = None


class AboutBase(ApiModel):
    name: str
    title: str
    tagline: str
    description: list[str]
    status: str
    images: AboutImages
    links: AboutLinks
    connect: list[str]


class AboutCreate(AboutBase):
    pass


class AboutUpdate(ApiModel):
    name: str | None = None
    title: str | None = None
    tagline: str | None = None
    description: list[str] | None = None
    status: str | None = None
    images: AboutImages | None = None
    links: AboutLinks | None = None
    connect: list[str] | None = None


class About(TimestampedResource):
    name: str
    title: str
    tagline: str
    description: list[str] = Field(default_factory=list)
    status: str = ""
    images: AboutImages = Field(default_factory=AboutImages)
    links: AboutLinks = Field(default_factory=AboutLinks)
    connect: list[str] = Field(default_factory=list)


class ExperienceBase(ApiModel):
    title: str
    company: str
    url: str
    period: str
    description: str
    technologies: list[str] = Field(default_factory=list)
    logo: Logo
    order: int = 0
    published: bool = True


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceUpdate(ApiModel):
    title: str | None = None
    company: str | None = None
    url: str | None = None
    period: str | None = None
    description: str | None = None
    technologies: list[str] | None = None
    logo: Logo | None = None
    order: int | None = None
    published: bool | None = None


class Experience(OrderedResource):
    title: str
    company: str
    url: str = ""
    period: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    logo: Logo | None = None


class EducationBase(ApiModel):
    course: str
    institution: str
    period: str
    description: str
    url: str
    logo: Logo
    order: int = 0
    published: bool = True


class EducationCreate(EducationBase):
    pass


class EducationUpdate(ApiModel):
    course: str | None = None
    institution: str | None = None
    period: str | None = None
    description: str | None = None
    url: str | None = None
    logo: Logo | None = None
    order: int | None = None
    published: bool | None = None


class Education(OrderedResource):
    course: str
    institution: str = ""
    period: str = ""
    description: str = ""
    url: str = ""
    logo: Logo | None = None


class ToolBase(ApiModel):
    name: str
    logo: Logo
    order: int = 0
    published: bool = True


class ToolCreate(ToolBase):
    pass


class ToolUpdate(ApiModel):
    name: str | None = None
    logo: Logo | None = None
    order: int | None = None
    published: bool | None = None


class Tool(OrderedResource):
    name: str
    logo: Logo | None = None


class CommunityBase(ApiModel):
    name: str
    role: str
    period: str
    description: str
    community_url: str | None = None
    logo: Logo
    current: bool = False
    order: int = 0
    published: bool = True


class CommunityCreate(CommunityBase):
    pass


class CommunityUpdate(ApiModel):
    name: str | None = None
    role: str | None = None
    period: str | None = None
    description: str | None = None
    community_url: str | None = None
    logo: Logo | None = None
    current: bool | None = None
    order: int | None = None
    published: bool | None = None


class Community(OrderedResource):
    name: str
    role: str = ""
    period: str = ""
    description: str = ""
    community_url: str | None = None
    logo: Logo | None = None
    current: bool = False


class VideoBase(ApiModel):
    title: str
    date: str
    link: str
    thumbnail: str
    order: int = 0
    published: bool = True


class VideoCreate(VideoBase):
    pass


class VideoUpdate(ApiModel):
    title: str | None = None
    date: str | None = None
    link: str | None = None
    thumbnail: str | None = None
    order: int | None = None
    published: bool | None = None


class Video(OrderedResource):
    title: str
    date: str = ""
    link: str = ""
    thumbnail: str = ""
