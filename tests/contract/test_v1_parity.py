"""Parity with the v1.2.0 NestJS API.

`AGENTS.md`: "Write contract tests against the current NestJS responses first,
then run them against FastAPI. That parity baseline is how the migration gets
proven rather than assumed."

The baseline is recorded here as the v1 route table read out of `src/`, plus the
response shapes v1 produced. Each case states what v2.0.0 does with it: kept
identical, kept behind a deprecation, or deliberately changed — and a
deliberate change names the reason, so nothing breaks by accident.
"""

from __future__ import annotations

from functools import lru_cache

import pytest
from httpx import AsyncClient

from app.main import create_app
from tests.types import Headers

# Every route the NestJS app served, read from src/*/**.controller.ts.
V1_ROUTES = [
    # `AppController` served this, returning the string "Hello World!".
    ("GET", "/"),
    ("POST", "/auth/sign-in"),
    ("GET", "/about"),
    ("POST", "/about"),
    ("PATCH", "/about"),
    ("DELETE", "/about"),
    *[
        (method, path)
        for resource in (
            "experiences",
            "educations",
            "tools",
            "communities",
            "videos",
            "events",
            "blogs",
        )
        for method, path in (
            ("GET", f"/{resource}"),
            ("POST", f"/{resource}"),
            ("GET", f"/{resource}/{{id}}"),
            ("PATCH", f"/{resource}/{{id}}"),
            ("DELETE", f"/{resource}/{{id}}"),
        )
    ],
    ("POST", "/blogs/sync"),
    ("POST", "/upload"),
    ("GET", "/upload"),
    ("DELETE", "/upload/{publicId}"),
]

# The v1 routes v2.0.0 does not serve, and why. Anything not listed here must
# still exist, in some form, or this file fails.
INTENTIONALLY_DROPPED = {
    ("POST", "/events"): "Writes moved to /sessions. /events survives read-only.",
    ("PATCH", "/events/{id}"): "Writes moved to /sessions.",
    ("DELETE", "/events/{id}"): "Writes moved to /sessions.",
    ("GET", "/events/{id}"): "Superseded by GET /sessions/{slug}.",
    ("GET", "/upload"): "Renamed to GET /uploads. The v1 path kept POST only.",
    ("DELETE", "/upload/{publicId}"): "Renamed to DELETE /uploads/{publicId}.",
}


@lru_cache
def _served_paths() -> frozenset[tuple[str, str]]:
    """The served surface, read from the OpenAPI spec.

    Not from `app.routes`: since FastAPI 0.141 `include_router` keeps routers
    nested rather than flattening them. The spec is the right source anyway —
    it is what both frontends generate their clients from.
    """
    spec = create_app().openapi()
    return frozenset(
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
    )


def _normalise(path: str) -> str:
    """v1 named its path parameter `id`; the factory names it `identifier`."""
    return (
        path.replace("{id}", "{identifier}")
        .replace("{publicId}", "{public_id}")
        .replace("/upload/", "/uploads/")
    )


@pytest.mark.parametrize(("method", "path"), V1_ROUTES)
def test_every_v1_route_is_served_or_deliberately_dropped(method: str, path: str) -> None:
    served = _served_paths()
    if (method, path) in INTENTIONALLY_DROPPED:
        pytest.skip(INTENTIONALLY_DROPPED[(method, path)])
    assert (method, _normalise(path)) in served, (
        f"{method} {path} existed in v1.2.0 and is not served by v2.0.0. "
        "Either implement it or record it in INTENTIONALLY_DROPPED with a reason."
    )


class TestDeliberateShapeChanges:
    """Places v2.0.0 returns something different, on purpose.

    Both consumers are rewritten in the same release, so these are adopted
    rather than absorbed. Each one is recorded in `CHANGELOG.md`.
    """

    async def test_lists_are_an_envelope_not_a_bare_array(self, client: AsyncClient) -> None:
        # v1: `Tool[]`. v2.0.0: one envelope on every collection endpoint.
        response = await client.get("/tools")
        body = response.json()
        assert set(body) == {"items", "total", "limit", "offset"}
        assert isinstance(body["items"], list)

    async def test_an_empty_collection_is_200_not_404(self, client: AsyncClient) -> None:
        # v1 threw NotFoundException when a list came back empty, so an empty
        # section was indistinguishable from a broken endpoint.
        response = await client.get("/videos")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}

    async def test_records_expose_id_not_underscore_id(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        created = await client.post(
            "/tools",
            headers=admin_headers,
            json={"name": "Docker", "logo": {"light": "l", "dark": "d"}},
        )
        body = created.json()
        assert "id" in body
        assert "_id" not in body
        assert "__v" not in body

    async def test_errors_use_the_new_envelope(self, client: AsyncClient) -> None:
        # v1: {statusCode, timestamp, path, message}.
        response = await client.get("/tools/000000000000000000000000")
        assert response.status_code == 404
        body = response.json()
        assert set(body) == {"error"}
        assert set(body["error"]) == {"code", "message", "details"}
        assert body["error"]["code"] == "not_found"

    async def test_the_root_returns_an_object_not_a_string(self, client: AsyncClient) -> None:
        # v1 returned the bare string "Hello World!". Nothing consumed it, and
        # a person who lands on the bare domain gets something useful instead.
        body = (await client.get("/")).json()
        assert isinstance(body, dict)
        assert body["name"] == "api.dileepa.dev"

    async def test_events_is_still_a_bare_array(self, client: AsyncClient) -> None:
        # The alias exists so nothing breaks mid-migration, so it keeps v1's
        # shape exactly — envelope included, or rather not included.
        response = await client.get("/events")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
