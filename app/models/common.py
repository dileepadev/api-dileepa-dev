"""Types shared by every resource.

The contract's "fields on every resource" rule lives here: `id`, `createdAt`,
`updatedAt`, `published`, `order`, `meta`.

**Naming.** Stored documents and the JSON API are camelCase; Python is
snake_case. One alias generator bridges the two, so `community_url` in Python is
`communityUrl` on the wire and in Mongo without a hand-written alias per field.
Requests accept either spelling; responses always emit camelCase.

Two notes that matter when reading v1 documents:

- **`order` replaces v1's `index`.** Both name the same thing and both mean
  *priority — higher sorts first*, which is why v1 sorted `index: -1`. Read
  models accept either name, so the API works against documents the backfill in
  `scripts/migrate_v1_documents.py` has not reached yet.
- **`published` is absent on every v1 document.** Missing means published:
  everything in the database today is live on the site.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from bson import ObjectId
from pydantic import (
    AliasChoices,
    AliasGenerator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
)
from pydantic.alias_generators import to_camel


def _to_str_id(value: Any) -> Any:
    return str(value) if isinstance(value, ObjectId) else value


# Mongo hands back an ObjectId; the API always exposes a string.
DocumentId = Annotated[str, BeforeValidator(_to_str_id)]

# A URL, validated as a string. Kept as `str` rather than `HttpUrl` because
# these values round-trip through Mongo and OpenAPI, and Pydantic's URL type
# normalises in ways that would silently rewrite stored values.
Url = str

_ALIASES = AliasGenerator(
    validation_alias=lambda name: AliasChoices(name, to_camel(name)),
    serialization_alias=to_camel,
)


class ApiModel(BaseModel):
    """Base for every request and response model."""

    model_config = ConfigDict(
        alias_generator=_ALIASES,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )


class ResponseModel(BaseModel):
    """Base for models built from a database document."""

    model_config = ConfigDict(
        alias_generator=_ALIASES,
        populate_by_name=True,
        str_strip_whitespace=True,
        # Responses are built from stored documents, which may carry fields an
        # older or newer release wrote. Ignoring them beats a 500.
        extra="ignore",
    )


class TimestampedResource(ResponseModel):
    id: DocumentId = Field(validation_alias=AliasChoices("id", "_id"))
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrderedResource(TimestampedResource):
    published: bool = True
    order: int = Field(
        default=0,
        validation_alias=AliasChoices("order", "index"),
        description="Priority. Higher values sort first.",
    )
    meta: dict[str, Any] = Field(default_factory=dict)


class Image(ApiModel):
    url: Url
    alt: str = ""


class Seo(ApiModel):
    meta_title: str | None = None
    meta_description: str | None = None
    og_image: Url | None = None


class Series(ApiModel):
    name: str
    order: int = 0


class Period(ApiModel):
    start: datetime
    end: datetime | None = None


class Metric(ApiModel):
    label: str
    value: str


class Logo(ApiModel):
    """A themed logo pair. Present on experiences, educations, tools, communities."""

    light: Url
    dark: Url


class ReorderItem(ApiModel):
    id: str
    order: int


class ReorderRequest(ApiModel):
    """Bulk reorder.

    One request per drag-and-drop commit, rather than one PATCH per row, which
    is what a list of any length would otherwise cost.
    """

    items: list[ReorderItem] = Field(min_length=1, max_length=500)


class ReorderResult(ApiModel):
    updated: int


class DeleteResult(ApiModel):
    id: str
    deleted: Literal[True] = True
