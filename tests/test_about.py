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
    "taglineDescription": "Mostly Python, mostly for people who have to run it.",
    "description": ["A paragraph.", "Another paragraph."],
    "status": "Open to work",
    "images": {
        "bannerWebp": "https://res.cloudinary.com/x/banner.webp",
        "profilePng": "https://res.cloudinary.com/x/profile.png",
        "profileWebp": "https://res.cloudinary.com/x/profile.webp",
        "profileJpg": "https://res.cloudinary.com/x/profile.jpg",
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

    async def test_the_hero_reads_one_record(self, client: AsyncClient) -> None:
        """The site's hero needs both halves, and must not need a second call.

        `taglineDescription` exists so the supporting line is a field rather
        than "the second paragraph of `description`" — a coupling nothing
        declared and nothing protected.
        """
        body = (await client.get("/about")).json()
        assert body["tagline"] == ABOUT["tagline"]
        assert body["taglineDescription"] == ABOUT["taglineDescription"]

    async def test_the_portrait_is_offered_in_three_formats(self, client: AsyncClient) -> None:
        images = (await client.get("/about")).json()["images"]
        assert images["profileWebp"].endswith(".webp")
        assert images["profileJpg"].endswith(".jpg")
        assert images["profilePng"].endswith(".png")

    async def test_a_jpeg_only_portrait_round_trips(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        """A record with no WebP and no PNG is a valid record.

        JPEG is not a fallback bolted onto the other two — it is a portrait
        format in its own right, and the API must not require a companion.
        """
        response = await client.patch(
            "/about",
            headers=admin_headers,
            json={"images": {"profileJpg": "https://res.cloudinary.com/x/only.jpeg"}},
        )
        assert response.status_code == 200
        images = response.json()["images"]
        assert images["profileJpg"] == "https://res.cloudinary.com/x/only.jpeg"
        assert images["profileWebp"] is None
        assert images["profilePng"] is None


class TestLegacyRecord:
    """A document written before either field existed still reads.

    Both are optional on the response model for this reason, and it is the same
    reason `location` is: a response model stricter than its request model
    turns a legitimately absent field into a 500 on read.
    """

    @pytest.fixture
    def seed(self) -> dict[str, list[dict[str, Any]]]:
        legacy = {
            key: value
            for key, value in ABOUT.items()
            if key not in {"taglineDescription", "images"}
        }
        legacy["images"] = {
            "bannerWebp": ABOUT["images"]["bannerWebp"],
            "profileWebp": ABOUT["images"]["profileWebp"],
        }
        return {"users": users_seed(), "about": [legacy]}

    async def test_it_reads_with_nulls_rather_than_failing(self, client: AsyncClient) -> None:
        response = await client.get("/about")
        assert response.status_code == 200
        body = response.json()
        assert body["taglineDescription"] is None
        assert body["images"]["profileJpg"] is None
        # And the formats that predate the change are untouched.
        assert body["images"]["profileWebp"] == ABOUT["images"]["profileWebp"]

    async def test_portrait_preference_order(self) -> None:
        """WebP, then JPEG, then PNG — smallest first, lossless last."""
        from app.models.profile import AboutImages

        every = AboutImages(profile_webp="w.webp", profile_jpg="j.jpg", profile_png="p.png")
        assert every.portrait_sources() == ["w.webp", "j.jpg", "p.png"]
        assert AboutImages(profile_jpg="j.jpg").portrait_sources() == ["j.jpg"]
        assert AboutImages().portrait_sources() == []
