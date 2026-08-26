"""Pagination, visibility, ordering and the error envelope.

These behaviours come from the factory, so testing them on one resource tests
them on all five. `test_openapi.py` asserts the five are actually identical.
"""

from __future__ import annotations

from typing import Any

import pytest
from bson import ObjectId
from httpx import AsyncClient

from tests.conftest import users_seed
from tests.types import Headers, Repos, must_find


@pytest.fixture
def seed() -> dict[str, list[dict[str, Any]]]:
    return {
        "users": users_seed(),
        "tools": [
            {"name": "Python", "index": 30, "logo": {"light": "l", "dark": "d"}},
            {"name": "Rust", "index": 20, "logo": {"light": "l", "dark": "d"}},
            {"name": "Zig", "index": 10, "logo": {"light": "l", "dark": "d"}},
            {
                "name": "Secret",
                "index": 99,
                "published": False,
                "logo": {"light": "l", "dark": "d"},
            },
        ],
    }


class TestVisibility:
    async def test_public_callers_do_not_see_unpublished_records(self, client: AsyncClient) -> None:
        body = (await client.get("/tools")).json()
        assert [item["name"] for item in body["items"]] == ["Python", "Rust", "Zig"]
        assert body["total"] == 3

    async def test_admin_sees_everything(self, client: AsyncClient, admin_headers: Headers) -> None:
        body = (await client.get("/tools", headers=admin_headers)).json()
        assert body["total"] == 4
        assert body["items"][0]["name"] == "Secret"

    async def test_admin_can_filter_to_unpublished(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        body = (await client.get("/tools?published=false", headers=admin_headers)).json()
        assert [item["name"] for item in body["items"]] == ["Secret"]

    async def test_a_public_published_filter_cannot_widen_visibility(
        self, client: AsyncClient
    ) -> None:
        body = (await client.get("/tools?published=false")).json()
        assert body["items"] == []

    async def test_fetching_an_unpublished_record_directly_is_a_404(
        self, client: AsyncClient, repositories: Repos
    ) -> None:
        secret = await must_find(repositories["tools"], {"name": "Secret"})
        response = await client.get(f"/tools/{secret['_id']}")
        assert response.status_code == 404

    async def test_an_admin_can_fetch_an_unpublished_record(
        self, client: AsyncClient, admin_headers: Headers, repositories: Repos
    ) -> None:
        secret = await must_find(repositories["tools"], {"name": "Secret"})
        response = await client.get(f"/tools/{secret['_id']}", headers=admin_headers)
        assert response.status_code == 200


class TestOrdering:
    async def test_higher_order_sorts_first(self, client: AsyncClient) -> None:
        # v1 sorted `index: -1`, meaning a priority. `order` keeps that meaning.
        body = (await client.get("/tools")).json()
        assert [item["order"] for item in body["items"]] == [30, 20, 10]

    async def test_a_v1_document_with_index_reads_as_order(self, client: AsyncClient) -> None:
        body = (await client.get("/tools")).json()
        assert body["items"][0]["order"] == 30
        assert "index" not in body["items"][0]

    async def test_a_migrated_collection_sorts_the_same_way(
        self, client: AsyncClient, repositories: Repos
    ) -> None:
        """After the backfill renames `index` to `order`, nothing changes."""
        for tool in repositories["tools"].documents:
            await repositories["tools"].update(str(tool["_id"]), {"order": tool.pop("index", 0)})
        body = (await client.get("/tools")).json()
        assert [item["name"] for item in body["items"]] == ["Python", "Rust", "Zig"]

    async def test_bulk_reorder(
        self, client: AsyncClient, admin_headers: Headers, repositories: Repos
    ) -> None:
        # Reordering happens from the admin, after the backfill, so every
        # document already carries `order`.
        for tool in repositories["tools"].documents:
            await repositories["tools"].update(str(tool["_id"]), {"order": tool.pop("index", 0)})
        tools = {t["name"]: str(t["_id"]) for t in repositories["tools"].documents}
        response = await client.patch(
            "/tools/order",
            headers=admin_headers,
            json={
                "items": [
                    {"id": tools["Zig"], "order": 99},
                    {"id": tools["Python"], "order": 1},
                ]
            },
        )
        assert response.status_code == 200
        assert response.json() == {"updated": 2}
        names = [item["name"] for item in (await client.get("/tools")).json()["items"]]
        assert names == ["Zig", "Rust", "Python"]

    async def test_reorder_needs_admin(self, client: AsyncClient, editor_headers: Headers) -> None:
        response = await client.patch(
            "/tools/order",
            headers=editor_headers,
            json={"items": [{"id": str(ObjectId()), "order": 1}]},
        )
        assert response.status_code == 403

    async def test_reorder_is_not_mistaken_for_a_record_id(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        # `/tools/order` must route to the reorder handler, not to `/tools/{id}`.
        response = await client.patch("/tools/order", headers=admin_headers, json={"items": []})
        assert response.status_code == 422


class TestPagination:
    async def test_limit_and_offset(self, client: AsyncClient) -> None:
        body = (await client.get("/tools?limit=2&offset=1")).json()
        assert [item["name"] for item in body["items"]] == ["Rust", "Zig"]
        assert body == {"items": body["items"], "total": 3, "limit": 2, "offset": 1}

    async def test_total_counts_matches_not_the_page(self, client: AsyncClient) -> None:
        body = (await client.get("/tools?limit=1")).json()
        assert len(body["items"]) == 1
        assert body["total"] == 3

    @pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "limit=abc"])
    async def test_bad_paging_is_rejected(self, client: AsyncClient, query: str) -> None:
        response = await client.get(f"/tools?{query}")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_failed"


class TestWrites:
    async def test_create_then_read_back(self, client: AsyncClient, admin_headers: Headers) -> None:
        created = await client.post(
            "/tools",
            headers=admin_headers,
            json={"name": "Elixir", "order": 5, "logo": {"light": "l.svg", "dark": "d.svg"}},
        )
        assert created.status_code == 201
        record = created.json()
        assert record["createdAt"] and record["updatedAt"]

        fetched = await client.get(f"/tools/{record['id']}")
        assert fetched.json()["name"] == "Elixir"

    async def test_patch_only_changes_what_was_sent(
        self, client: AsyncClient, admin_headers: Headers, repositories: Repos
    ) -> None:
        tool = await must_find(repositories["tools"], {"name": "Rust"})
        response = await client.patch(
            f"/tools/{tool['_id']}", headers=admin_headers, json={"order": 77}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["order"] == 77
        assert body["name"] == "Rust"
        assert body["logo"] == {"light": "l", "dark": "d"}

    async def test_delete(
        self, client: AsyncClient, admin_headers: Headers, repositories: Repos
    ) -> None:
        tool = await must_find(repositories["tools"], {"name": "Zig"})
        response = await client.delete(f"/tools/{tool['_id']}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json() == {"id": str(tool["_id"]), "deleted": True}
        assert (await client.get(f"/tools/{tool['_id']}")).status_code == 404

    async def test_a_duplicate_unique_field_is_a_409(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post(
            "/tools",
            headers=admin_headers,
            json={"name": "Python", "logo": {"light": "l", "dark": "d"}},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    async def test_unknown_fields_are_rejected(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        # v1 used forbidNonWhitelisted; the same posture is kept.
        response = await client.post(
            "/tools",
            headers=admin_headers,
            json={"name": "Nim", "logo": {"light": "l", "dark": "d"}, "colour": "red"},
        )
        assert response.status_code == 422


class TestErrorEnvelope:
    async def test_not_found(self, client: AsyncClient) -> None:
        response = await client.get(f"/tools/{ObjectId()}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    async def test_a_malformed_id_is_a_404_not_a_500(self, client: AsyncClient) -> None:
        response = await client.get("/tools/not-an-object-id")
        assert response.status_code == 404

    async def test_validation_errors_name_the_fields(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post("/tools", headers=admin_headers, json={})
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "validation_failed"
        assert {item["field"] for item in error["details"]} == {"name", "logo"}

    async def test_method_not_allowed(self, client: AsyncClient) -> None:
        response = await client.put("/tools")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"

    async def test_no_message_is_something_went_wrong(self, client: AsyncClient) -> None:
        # The voice rules apply to error text: it surfaces in the admin UI.
        response = await client.get(f"/tools/{ObjectId()}")
        assert "something went wrong" not in response.json()["error"]["message"].lower()


class TestSecurityHeaders:
    async def test_headers_are_present(self, client: AsyncClient) -> None:
        response = await client.get("/tools")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Strict-Transport-Security" in response.headers
        assert response.headers["Content-Security-Policy"].startswith("default-src 'none'")
