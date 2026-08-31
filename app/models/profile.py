"""The profile resources.

Field names and types match the existing documents exactly. The only additions
are the platform-wide fields from `OrderedResource`, all optional with defaults,
so these models read a v1 document without a migration having run first.

`about` is a singleton: one document, no `order`, no list endpoint.

`pillars` and `speaking_topics` are new in v2.0.0 and have no v1 shape to
match. Both replace copy that was compiled into the website — the six cards in
its About section and the talk themes on its speaker kit — so that editing
either is a save in the admin rather than a deploy.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.common import ApiModel, Logo, OrderedResource, TimestampedResource, Url


class AboutImages(ApiModel):
    """The portrait, in every format it has been uploaded in.

    Three portrait fields rather than one, because a consumer picks the format
    it wants rather than the one that happens to be stored: `next/image` is
    happiest with WebP, a JPEG is what a phone camera and most stock exports
    produce, and the PNG is the lossless original. All three are optional and
    a record may carry any subset — `portrait_sources()` is the order they are
    preferred in.
    """

    banner_webp: Url | None = None
    profile_png: Url | None = None
    profile_webp: Url | None = None
    # New in v2.0.0. WebP and PNG both predate it, and neither changes: a
    # record with no JPEG behaves exactly as it did before this field existed.
    profile_jpg: Url | None = None

    def portrait_sources(self) -> list[Url]:
        """The portrait URLs to try, most preferred first.

        Smallest first, lossless last. The JPEG slots between WebP and PNG,
        which is why adding it changes nothing for a record that has neither
        of the other two or has the WebP: the existing answer stays the
        existing answer.
        """
        return [url for url in (self.profile_webp, self.profile_jpg, self.profile_png) if url]


class AboutLinks(ApiModel):
    website: str | None = None
    email: str | None = None
    github: str | None = None
    linkedin: str | None = None
    xtwitter: str | None = None
    instagram: str | None = None
    youtube: str | None = None
    facebook: str | None = None


class AboutBase(ApiModel):
    name: str | None = None
    title: str | None = None
    tagline: str | None = None
    # The sentence under the tagline in the hero. It lived in `description[1]`,
    # which meant the site had to know that the About section's second
    # paragraph was also the hero's lead — a coupling nothing declared and
    # nothing protected. It is its own field so the hero reads one value and
    # the About copy can be edited without moving the hero out from under it.
    tagline_description: str | None = None
    # Rendered beside the portrait as "<title> · <location>". Free text rather
    # than a structured place: it is a label on a photograph, not an address.
    location: str | None = None
    description: list[str] | None = None
    # The two speaker biographies the media kit at /profile hands to an event
    # organiser, verbatim and copyable. They are here rather than in a resource
    # of their own because they are the same person this record already
    # describes, said at two lengths — a name, a title and a location that
    # disagreed with the bio beside them would be worse than either.
    short_bio: str | None = None
    full_bio: str | None = None
    status: str | None = None
    images: AboutImages
    links: AboutLinks
    connect: list[str] | None = None


class AboutCreate(AboutBase):
    pass


class AboutUpdate(ApiModel):
    name: str | None = None
    title: str | None = None
    tagline: str | None = None
    tagline_description: str | None = None
    location: str | None = None
    description: list[str] | None = None
    short_bio: str | None = None
    full_bio: str | None = None
    status: str | None = None
    images: AboutImages | None = None
    links: AboutLinks | None = None
    connect: list[str] | None = None


class About(TimestampedResource):
    name: str
    title: str
    tagline: str
    # Optional on the way out for the same reason `location` is: every record
    # written before the field existed has no value for it, and a response
    # model stricter than its request model turns that into a 500 on read.
    tagline_description: str | None = None
    # Optional on the way out because it is optional on the way in. A response
    # model stricter than its request model turns a legitimately-absent field
    # into a 500 on read, which is what `location: str` did to every record
    # written before the field existed.
    location: str | None = None
    description: list[str] = Field(default_factory=list)
    # Optional on the way out for the same reason `location` is: every record
    # written before these existed has no value for either, and the site falls
    # back to its own copy when they are absent.
    short_bio: str | None = None
    full_bio: str | None = None
    status: str | None = None
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
    #: One or two sentences shown under the title in the site's list. Optional,
    #: because every row that predates this field has nothing to put in it and
    #: a required field would make each one fail validation on read.
    description: str = ""
    order: int = 0
    published: bool = True


class VideoCreate(VideoBase):
    pass


class VideoUpdate(ApiModel):
    title: str | None = None
    date: str | None = None
    link: str | None = None
    thumbnail: str | None = None
    description: str | None = None
    order: int | None = None
    published: bool | None = None


class Video(OrderedResource):
    title: str
    date: str = ""
    link: str = ""
    thumbnail: str = ""
    description: str = ""


# The icon a pillar card renders, named rather than drawn.
#
# A closed set, not free text, for two reasons: the admin renders it as a
# select rather than a box you can typo into, and the website resolves each
# name to an imported icon component — a name it does not know would render
# nothing. Adding one means adding it here *and* to the site's map; the site
# falls back to `cpu` so a mismatch is a wrong icon rather than a blank card.
PillarIcon = Literal[
    "cpu",
    "code",
    "mic",
    "book",
    "video",
    "users",
    "sparkles",
    "rocket",
    "terminal",
    "pen",
    "globe",
    "graduation-cap",
]


class PillarBase(ApiModel):
    """One card in the website's About section.

    Six of them describe what Dileepa does — AI engineering, open source,
    speaking, writing, videos, community. They were a constant in the site's
    `lib/constants.ts` until v2.0.0, which meant rewording a card was a pull
    request and a deploy.
    """

    title: str
    description: str
    icon: PillarIcon = "cpu"
    order: int = 0
    published: bool = True


class PillarCreate(PillarBase):
    pass


class PillarUpdate(ApiModel):
    title: str | None = None
    description: str | None = None
    icon: PillarIcon | None = None
    order: int | None = None
    published: bool | None = None


class Pillar(OrderedResource):
    title: str
    description: str = ""
    icon: PillarIcon = "cpu"


class SpeakingTopicBase(ApiModel):
    """One talk or workshop theme on the speaker kit at /profile.

    The "sessions and talks" section an event organiser reads to see what
    Dileepa presents on. Like `pillars`, this was site copy first; unlike
    `pillars` it changes often, because the list follows whatever is actually
    being delivered that season.
    """

    title: str
    summary: str
    order: int = 0
    published: bool = True


class SpeakingTopicCreate(SpeakingTopicBase):
    pass


class SpeakingTopicUpdate(ApiModel):
    title: str | None = None
    summary: str | None = None
    order: int | None = None
    published: bool | None = None


class SpeakingTopic(OrderedResource):
    title: str
    summary: str = ""
