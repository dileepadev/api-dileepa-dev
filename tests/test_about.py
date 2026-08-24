"""About — the singleton. No id in any path, and no list endpoint."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import users_seed
from tests.types import Headers

ABOUT: dict[str, Any] = {
    "name": "Dileepa Bandara",
    "title": "Associate AI Engineer",
    "tagline": "I build things and write about how they went.",
    "description": ["A paragraph.", "Another paragraph."],
    "status": "Open to work",
    "images": {
        "bannerWebp": "https://res.cloudinary.com/x/banner.webp",
        "profilePng": "https://res.cloudinary.com/x/profile.png",
        "profileWebp": "https://res.cloudinary.com/x/profile.webp",
    },
    "links": {
        "website": "https://dileepa.dev",
        "email": "contact@dileepa.dev",
        "github": "https://github.com/dileepadev",
        "linkedin": "https://linkedin.com/in/dileepadev",
        "xtwitter": "https://x.com/dileepadev",
        "instagram": "https://instagram.com/dileepadev",
        "youtube": "https://youtube.com/@dileepadev",
    },
    "connect": ["Say hello."],
}


class TestEmpty:
    @pytest.fixture
    def seed(self) -> dict[str, list[dict[str, Any]]]:
        return {"users": users_seed()}

    async def test_reading_before_one_exists_says_how_to_create_it(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/about")
        assert response.status_code == 404
        assert "POST /about" in response.json()["error"]["message"]

    async def test_create(self, client: AsyncClient, admin_headers: Headers) -> None:
        response = await client.post("/about", headers=admin_headers, json=ABOUT)
        assert response.status_code == 201
        body = response.json()
        assert body["images"]["bannerWebp"] == ABOUT["images"]["bannerWebp"]
        assert body["id"]

    async def test_patching_before_one_exists_is_a_404(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.patch("/about", headers=admin_headers, json={"name": "X"})
        assert response.status_code == 404


class TestExisting:
    @pytest.fixture
    def seed(self) -> dict[str, list[dict[str, Any]]]:
        return {"users": users_seed(), "about": [dict(ABOUT)]}

    async def test_read_is_public(self, client: AsyncClient) -> None:
        response = await client.get("/about")
        assert response.status_code == 200
        assert response.json()["name"] == "Dileepa Bandara"

    async def test_a_second_record_is_refused(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post("/about", headers=admin_headers, json=ABOUT)
        assert response.status_code == 409
        assert "PATCH /about" in response.json()["error"]["message"]

    async def test_patch_is_partial(self, client: AsyncClient, admin_headers: Headers) -> None:
        response = await client.patch("/about", headers=admin_headers, json={"status": "Building"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "Building"
        assert body["name"] == "Dileepa Bandara"

    async def test_an_empty_patch_changes_nothing(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.patch("/about", headers=admin_headers, json={})
        assert response.status_code == 200
        assert response.json()["name"] == "Dileepa Bandara"

    async def test_writes_need_admin(self, client: AsyncClient, editor_headers: Headers) -> None:
        assert (await client.patch("/about", headers=editor_headers, json={})).status_code == 403
        assert (await client.delete("/about", headers=editor_headers)).status_code == 403

    async def test_delete(self, client: AsyncClient, admin_headers: Headers) -> None:
        response = await client.delete("/about", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["deleted"] is True
        assert (await client.get("/about")).status_code == 404

    async def test_there_is_no_list_endpoint(self, client: AsyncClient) -> None:
        # A singleton with a `?limit=` would invite a second record.
        body = (await client.get("/about")).json()
        assert "items" not in body
