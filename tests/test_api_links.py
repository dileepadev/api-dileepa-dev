"""`GET /api-links` — the endpoint catalogue the admin dashboard renders.

Two properties matter and neither is about the JSON. It has to be **derived**,
so it cannot describe an API that is not the one being served; and it has to be
**closed to the public**, because the reason it exists is that the admin needs
it and the website must not have it.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.core.routes import type_name
from tests.types import Headers


@pytest.fixture
async def links(client: AsyncClient, admin_headers: Headers) -> dict[str, Any]:
    response = await client.get("/api-links", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    return {group["key"]: group for group in body["items"]}


class TestAccess:
    async def test_it_needs_a_token(self, client: AsyncClient) -> None:
        """This is what keeps it off the public site rather than a convention.

        dileepa.dev holds no credentials and never will, so an endpoint behind
        an admin token is one the website cannot render even by mistake.
        """
        response = await client.get("/api-links")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "missing_token"

    async def test_a_non_admin_is_refused(
        self, client: AsyncClient, editor_headers: Headers
    ) -> None:
        response = await client.get("/api-links", headers=editor_headers)
        assert response.status_code == 403


class TestEnvelope:
    async def test_it_uses_the_one_list_envelope(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        body = (await client.get("/api-links", headers=admin_headers)).json()
        assert set(body) == {"items", "total", "limit", "offset"}

    async def test_it_pages(self, client: AsyncClient, admin_headers: Headers) -> None:
        body = (await client.get("/api-links?limit=2", headers=admin_headers)).json()
        assert len(body["items"]) == 2
        assert body["total"] > 2


class TestDerivedFromTheRoutes:
    async def test_every_tag_is_a_group(self, links: dict[str, Any]) -> None:
        # Including its own, which is the point: the catalogue does not get to
        # describe a surface it is not part of.
        for tag in ("about", "communities", "events", "blogs", "uploads", "api-links"):
            assert tag in links

    async def test_a_group_carries_its_path_and_its_description(
        self, links: dict[str, Any]
    ) -> None:
        communities = links["communities"]
        assert communities["basePath"] == "/communities"
        assert communities["label"] == "Communities"
        assert communities["description"] == "Community involvement."

    async def test_urls_are_absolute_against_the_host_that_answered(
        self, links: dict[str, Any]
    ) -> None:
        """No base URL to configure means no base URL to get wrong."""
        assert links["about"]["url"] == "http://testserver/about"
        assert links["about"]["endpoints"][0]["url"].startswith("http://testserver/")

    async def test_path_placeholders_survive(self, links: dict[str, Any]) -> None:
        paths = {endpoint["path"] for endpoint in links["communities"]["endpoints"]}
        assert "/communities/{identifier}" in paths
        # The path converter is Starlette's, not part of the contract.
        upload_paths = {endpoint["path"] for endpoint in links["uploads"]["endpoints"]}
        assert "/uploads/{public_id}" in upload_paths

    async def test_the_reorder_route_is_not_swallowed_by_the_placeholder(
        self, links: dict[str, Any]
    ) -> None:
        paths = {endpoint["path"] for endpoint in links["communities"]["endpoints"]}
        assert "/communities/order" in paths


class TestParameters:
    async def test_pagination_is_listed_even_though_a_dependency_declares_it(
        self, links: dict[str, Any]
    ) -> None:
        """A caller that cannot see `limit` and `offset` cannot page."""
        listing = next(
            endpoint
            for endpoint in links["communities"]["endpoints"]
            if endpoint["method"] == "GET" and endpoint["path"] == "/communities"
        )
        query = {p["name"] for p in listing["parameters"] if p["location"] == "query"}
        assert {"limit", "offset", "published"} <= query

    async def test_a_body_is_expanded_into_the_fields_it_accepts(
        self, links: dict[str, Any]
    ) -> None:
        """`payload: CommunityCreate` answers nothing. Its fields answer it."""
        create = next(
            endpoint
            for endpoint in links["communities"]["endpoints"]
            if endpoint["method"] == "POST"
        )
        body = {p["name"]: p for p in create["parameters"] if p["location"] == "body"}
        assert "payload" not in body
        assert body["name"]["required"] is True
        assert body["published"]["required"] is False
        # camelCase, because that is what goes over the wire.
        assert "communityUrl" in body
        assert "community_url" not in body

    async def test_the_new_about_fields_are_advertised(self, links: dict[str, Any]) -> None:
        patch = next(
            endpoint for endpoint in links["about"]["endpoints"] if endpoint["method"] == "PATCH"
        )
        body = {p["name"] for p in patch["parameters"] if p["location"] == "body"}
        assert "taglineDescription" in body

    async def test_a_multipart_endpoint_lists_its_form_fields(self, links: dict[str, Any]) -> None:
        upload = next(
            endpoint for endpoint in links["uploads"]["endpoints"] if endpoint["method"] == "POST"
        )
        body = {p["name"]: p for p in upload["parameters"] if p["location"] == "body"}
        assert body["file"]["type"] == "file"
        assert "JPEG" in (body["file"]["description"] or "")


class TestAuthLabels:
    async def test_a_public_read_is_not_reported_as_admin_only(self, links: dict[str, Any]) -> None:
        """The dependency graph, not the generated `security` block.

        Every endpoint that can *optionally* recognise an admin declares the
        same bearer scheme as one that requires it, so reading `security`
        would report `GET /communities` as closed when it is open.
        """
        listing = next(
            endpoint
            for endpoint in links["communities"]["endpoints"]
            if endpoint["method"] == "GET" and endpoint["path"] == "/communities"
        )
        assert listing["auth"] == "public"

    async def test_a_write_is_admin(self, links: dict[str, Any]) -> None:
        create = next(
            endpoint
            for endpoint in links["communities"]["endpoints"]
            if endpoint["method"] == "POST"
        )
        assert create["auth"] == "admin"

    async def test_the_blog_sync_is_api_key(self, links: dict[str, Any]) -> None:
        sync = next(
            endpoint
            for endpoint in links["blogs"]["endpoints"]
            if endpoint["path"] == "/blogs/sync"
        )
        assert sync["auth"] == "api_key"

    async def test_uploads_takes_either(self, links: dict[str, Any]) -> None:
        upload = next(
            endpoint for endpoint in links["uploads"]["endpoints"] if endpoint["method"] == "POST"
        )
        assert upload["auth"] == "admin_or_api_key"


class TestTypeNames:
    """Rendered for a person, so `str | None` is "string", not an `anyOf`."""

    @pytest.mark.parametrize(
        ("annotation", "expected"),
        [
            (str, "string"),
            (int, "integer"),
            (bool, "boolean"),
            (str | None, "string"),
            (list[str], "string[]"),
            (dict[str, int], "object"),
            (None, "null"),
        ],
    )
    def test_readable_names(self, annotation: Any, expected: str) -> None:
        assert type_name(annotation) == expected
