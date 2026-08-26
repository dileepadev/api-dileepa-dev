"""The API's own surface, described — what `GET /api-links` returns.

The admin dashboard shows, on each screen, the endpoint that screen talks to
and the variables it expects. That used to mean reading `lib/api.ts` next to
`app/routers/`, in two repositories, and trusting that the pair still agreed.
It is data now, and the API is the one that has it.

Nothing on the public website reads this. It is an admin-only endpoint and it
describes routes rather than serving content.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.common import ApiModel, Url

#: How a caller proves it may use an endpoint.
#:
#: `admin_or_api_key` is real and is not a shorthand for "either will do" —
#: `POST /uploads` takes an admin token from the dashboard or the pipeline's
#: `x-api-key` header, and nothing else in the platform does both.
AuthRequirement = Literal["public", "admin", "api_key", "admin_or_api_key"]

ParameterLocation = Literal["path", "query", "header", "body"]


class EndpointParameter(ApiModel):
    """One variable an endpoint reads, named the way it goes over the wire."""

    name: str
    location: ParameterLocation
    # A readable type rather than a JSON Schema fragment: this is rendered in a
    # table for a person, and `{"anyOf": [{"type": "string"}, …]}` is not.
    type: str = "string"
    required: bool = False
    description: str | None = None


class Endpoint(ApiModel):
    method: str
    #: The routed path, placeholders intact: `/communities/{identifier}`.
    path: str
    #: The same path against the host this response was served from.
    url: Url
    summary: str = ""
    auth: AuthRequirement = "public"
    parameters: list[EndpointParameter] = Field(default_factory=list)


class ApiLink(ApiModel):
    """Every endpoint under one tag — which is one admin screen's worth."""

    #: The OpenAPI tag. The admin keys its screens off this.
    key: str
    label: str
    description: str = ""
    #: The shortest path in the group — `/communities` for the communities tag.
    base_path: str
    url: Url
    #: The reference, anchored at this tag. Null in production, where the
    #: reference is not served and a link to it would be a dead one.
    docs_url: Url | None = None
    endpoints: list[Endpoint] = Field(default_factory=list)
