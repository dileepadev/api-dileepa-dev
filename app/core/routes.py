"""Reading the application's own route table.

Two things need this. The rate limiter has to find the handler for a request,
and `GET /api-links` has to describe every endpoint the API serves. Both run
into the same thing: since FastAPI 0.141 `include_router` keeps each router
nested as an `_IncludedRouter` rather than flattening its routes into the app,
so `app.routes` is a list of routers with one real route in it — the docs page.

That knowledge lives here once. Two copies of it is how one of them gets fixed.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, datetime
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from fastapi import FastAPI, UploadFile
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from pydantic import BaseModel
from starlette.routing import BaseRoute

from app.core.deps import api_key_or_admin, require_admin, require_api_key
from app.models.api_links import ApiLink, Endpoint, EndpointParameter

#: Rendered instead of the Python name. Everything else falls back to the
#: class name, which is right for a model — `AboutUpdate` is what a person
#: needs to see.
_SCALARS: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    bytes: "binary",
    datetime: "date-time",
    date: "date",
    UploadFile: "file",
}

#: Starlette's path converter, as it appears in a declared route. The spec
#: publishes `/uploads/{public_id}`, so the catalogue does too.
_CONVERTER = re.compile(r"\{([^{}:]+):[^{}]+\}")

#: Parameters every caller sends and nobody needs told about. `limit` and
#: `offset` are deliberately *not* here: they are the pagination contract, and
#: an admin screen listing 200 records needs to know they exist.
_UNINTERESTING = {"authorization", "accept", "content-type", "user-agent"}


def flatten_routes(routes: list[BaseRoute]) -> Iterator[BaseRoute]:
    """Yield real routes, descending into the routers FastAPI keeps nested.

    An `_IncludedRouter` carries the router it wrapped on `.original_router`.
    The routes inside it keep their full path — `/auth/login`, not `/login` —
    so matching or reading them directly is equivalent to what the app does.
    """
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is None:
            yield route
        else:
            yield from flatten_routes(nested.routes)


def type_name(annotation: Any) -> str:
    """A readable type for a person reading a table, not a JSON Schema."""
    if annotation is None or annotation is type(None):
        return "null"

    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        # `str | None` reads as an optional string; the `required` column is
        # what says so, and repeating it in the type is noise.
        parts = [type_name(arg) for arg in get_args(annotation) if arg is not type(None)]
        return " or ".join(dict.fromkeys(parts)) or "null"
    if origin is Literal:
        return " or ".join(str(arg) for arg in get_args(annotation))
    if origin in (list, set, tuple, frozenset):
        args = get_args(annotation)
        return f"{type_name(args[0]) if args else 'any'}[]"
    if origin is dict:
        return "object"

    if isinstance(annotation, type):
        return _SCALARS.get(annotation, annotation.__name__)
    return str(annotation)


def _auth_of(dependant: Dependant) -> str:
    """What an endpoint asks a caller to prove, read off its dependencies.

    The dependency graph rather than the generated `security` block, because
    every endpoint that can *optionally* recognise an admin declares the same
    bearer scheme as one that requires it — `GET /communities` would otherwise
    describe itself as admin-only.
    """
    calls: set[Any] = set()
    stack = [dependant]
    while stack:
        current = stack.pop()
        if current.call is not None:
            calls.add(current.call)
        stack.extend(current.dependencies)

    if api_key_or_admin in calls:
        return "admin_or_api_key"
    if require_api_key in calls:
        return "api_key"
    if require_admin in calls:
        return "admin"
    return "public"


def _expand_body(annotation: Any) -> list[EndpointParameter]:
    """A request model, flattened into the fields it actually accepts.

    Named `payload` in the signature and `AboutUpdate` in the spec, neither of
    which answers "what do I send". Its fields do, under the names they travel
    as — camelCase, because that is what goes over the wire.
    """
    if not (isinstance(annotation, type) and issubclass(annotation, BaseModel)):
        return []
    return [
        EndpointParameter(
            name=str(field.serialization_alias or field.alias or name),
            location="body",
            type=type_name(field.annotation),
            required=field.is_required(),
            description=field.description,
        )
        for name, field in annotation.model_fields.items()
    ]


def _flatten_params(dependant: Dependant) -> dict[str, list[Any]]:
    """Every parameter the endpoint and its dependencies read, by location.

    Flat, because the parameters a dependency contributes are still parameters
    a caller sends: `limit` and `offset` come from `list_params` and are the
    whole pagination contract. A caller that cannot see them cannot page.
    """
    collected: dict[str, list[Any]] = {"path": [], "query": [], "header": [], "body": []}
    stack = [dependant]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        collected["path"].extend(current.path_params)
        collected["query"].extend(current.query_params)
        collected["header"].extend(current.header_params)
        collected["body"].extend(current.body_params)
        stack.extend(reversed(current.dependencies))
    return collected


def _parameters(route: APIRoute) -> list[EndpointParameter]:
    collected = _flatten_params(route.dependant)
    parameters: list[EndpointParameter] = []

    for location in ("path", "query", "header"):
        for field in collected[location]:
            name = str(field.alias or field.name)
            if location == "header" and name.lower() in _UNINTERESTING:
                continue
            parameters.append(
                EndpointParameter(
                    name=name,
                    location=location,
                    type=type_name(field.field_info.annotation),
                    required=field.field_info.is_required(),
                    description=field.field_info.description,
                )
            )

    for field in collected["body"]:
        expanded = _expand_body(field.field_info.annotation)
        if expanded:
            parameters.extend(expanded)
            continue
        # A multipart endpoint has no model to expand — `POST /uploads` takes
        # `file`, `folder` and `public_id` as form fields.
        parameters.append(
            EndpointParameter(
                name=str(field.alias or field.name),
                location="body",
                type=type_name(field.field_info.annotation),
                required=field.field_info.is_required(),
                description=field.field_info.description,
            )
        )

    # Two dependencies can declare the same parameter — the same one, not two.
    # Deduplicated on the pair a reader sees rather than on identity, which
    # would keep both copies.
    unique: dict[tuple[str, str], EndpointParameter] = {}
    for parameter in parameters:
        unique.setdefault((parameter.location, parameter.name), parameter)
    return list(unique.values())


def _label(tag: str) -> str:
    """`api-links` → "API links". Sentence case, per the brand rules."""
    words = tag.replace("-", " ").replace("_", " ").strip()
    label = words[:1].upper() + words[1:]
    return label.replace("Api", "API")


def catalogue(app: FastAPI, *, base_url: str, docs_url: str | None = None) -> list[ApiLink]:
    """Describe every endpoint the app serves, grouped by tag.

    Built from the live route table, so it cannot drift from what is served —
    which is the only reason it is worth publishing at all. A hand-written
    list of endpoints is a second contract, and the second one is always the
    one that is wrong.
    """
    base = base_url.rstrip("/")
    descriptions = {
        str(tag["name"]): str(tag.get("description", "")) for tag in (app.openapi_tags or [])
    }
    # The order tags are declared in is the order they are meant to be read in.
    order = {name: index for index, name in enumerate(descriptions)}

    grouped: dict[str, list[Endpoint]] = {}
    for route in flatten_routes(app.routes):
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        tag = str(route.tags[0]) if route.tags else "other"
        auth = _auth_of(route.dependant)
        parameters = _parameters(route)
        path = _CONVERTER.sub(r"{\1}", route.path)
        for method in sorted((route.methods or set()) - {"HEAD", "OPTIONS"}):
            grouped.setdefault(tag, []).append(
                Endpoint(
                    method=method,
                    path=path,
                    url=f"{base}{path}",
                    summary=route.summary or "",
                    auth=auth,
                    parameters=parameters,
                )
            )

    links = [
        ApiLink(
            key=tag,
            label=_label(tag),
            description=descriptions.get(tag, ""),
            base_path=min((endpoint.path for endpoint in endpoints), key=len),
            url=f"{base}{min((e.path for e in endpoints), key=len)}",
            docs_url=f"{docs_url}#tag/{tag}" if docs_url else None,
            endpoints=endpoints,
        )
        for tag, endpoints in grouped.items()
    ]
    links.sort(key=lambda link: (order.get(link.key, len(order)), link.key))
    return links
