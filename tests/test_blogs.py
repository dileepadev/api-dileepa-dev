"""Blogs and the sync pipeline."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import users_seed
from tests.types import Headers, Repos, must_find


@pytest.fixture
def seed() -> dict[str, list[dict[str, Any]]]:
    return {
        "users": users_seed(),
        "blogs": [
            # A v1 row, exactly as the NestJS sync script wrote it: absolute
            # URLs on the old host, a string date, no path, no published flag.
            {
                "slug": "2026-02-27-running-ollama-ai-models-on-a-midrange-laptop",
                "title": "Running Ollama on a midrange laptop",
                "excerpt": "What actually ran, and how slowly.",
                "date": "2026-02-27",
                "index": 18,
                "link": "https://blog.dileepa.dev/blog/2026-02-27-running-ollama-ai-models-on-a-midrange-laptop",
                "bannerUrl": "https://dileepadev.blob.core.windows.net/images/banners/ollama.png",
            },
            {
                "slug": "2026-08-06-part-1-kicking-off-the-series",
                "title": "Kicking off the series",
                "description": "Part one.",
                "path": "/blog/2026-08-06-part-1-kicking-off-the-series",
                "publishedDate": "2026-08-06T00:00:00Z",
                "tags": ["ai", "azure"],
                "series": {"name": "Zero to agent", "order": 1},
                "order": 20,
                "published": True,
            },
        ],
    }


class TestReading:
    async def test_a_v1_row_gets_a_relative_path_and_a_canonical_url(
        self, client: AsyncClient
    ) -> None:
        """The API is correct before the URL migration has run."""
        response = await client.get(
            "/blogs/2026-02-27-running-ollama-ai-models-on-a-midrange-laptop"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["path"] == "/blog/2026-02-27-running-ollama-ai-models-on-a-midrange-laptop"
        assert body["canonicalUrl"] == (
            "https://dileepa.dev/blog/2026-02-27-running-ollama-ai-models-on-a-midrange-laptop"
        )
        assert "blog.dileepa.dev" not in body["path"]

    async def test_lookup_by_slug_and_by_id(self, client: AsyncClient, repositories: Repos) -> None:
        record = await must_find(
            repositories["blogs"], {"slug": "2026-08-06-part-1-kicking-off-the-series"}
        )
        by_id = await client.get(f"/blogs/{record['_id']}")
        by_slug = await client.get("/blogs/2026-08-06-part-1-kicking-off-the-series")
        assert by_id.json()["id"] == by_slug.json()["id"]

    async def test_filter_by_tag(self, client: AsyncClient) -> None:
        body = (await client.get("/blogs?tag=azure")).json()
        assert body["total"] == 1
        assert body["items"][0]["slug"] == "2026-08-06-part-1-kicking-off-the-series"

    async def test_filter_by_series(self, client: AsyncClient) -> None:
        body = (await client.get("/blogs?series=Zero+to+agent")).json()
        assert body["total"] == 1

    async def test_unknown_slug_is_a_404(self, client: AsyncClient) -> None:
        response = await client.get("/blogs/no-such-post")
        assert response.status_code == 404
        assert "no-such-post" in response.json()["error"]["message"]


class TestSync:
    def payload(self, **overrides: Any) -> dict[str, Any]:
        return {
            "slug": "2026-09-01-a-new-post",
            "title": "A new post",
            "description": "Written in the blog repo.",
            "publishedDate": "2026-09-01T09:00:00Z",
            "tags": ["python"],
            "banner": {
                "url": "https://res.cloudinary.com/x/image/upload/v1/blog/banners/2026-09-01.png",
                "alt": "Banner",
            },
            "readingTimeMinutes": 7,
            "sourcePath": "content/posts/2026-09-01-a-new-post.mdx",
            "contentHash": "abc123",
            **overrides,
        }

    async def test_creates_a_post(self, client: AsyncClient, api_key_headers: Headers) -> None:
        response = await client.post("/blogs/sync", headers=api_key_headers, json=self.payload())
        assert response.status_code == 200
        body = response.json()
        assert body["path"] == "/blog/2026-09-01-a-new-post"
        assert body["canonicalUrl"] == "https://dileepa.dev/blog/2026-09-01-a-new-post"
        assert body["published"] is True

    async def test_is_idempotent(self, client: AsyncClient, api_key_headers: Headers) -> None:
        first = await client.post("/blogs/sync", headers=api_key_headers, json=self.payload())
        second = await client.post(
            "/blogs/sync", headers=api_key_headers, json=self.payload(title="Retitled")
        )
        assert first.json()["id"] == second.json()["id"]
        assert second.json()["title"] == "Retitled"
        assert (await client.get("/blogs")).json()["total"] == 3

    async def test_draft_gates_visibility(
        self, client: AsyncClient, api_key_headers: Headers
    ) -> None:
        """`published = not draft`: front matter stays the one place this is decided."""
        await client.post("/blogs/sync", headers=api_key_headers, json=self.payload(draft=True))
        listed = (await client.get("/blogs")).json()
        assert "2026-09-01-a-new-post" not in [item["slug"] for item in listed["items"]]
        assert (await client.get("/blogs/2026-09-01-a-new-post")).status_code == 404

    async def test_undrafting_publishes(
        self, client: AsyncClient, api_key_headers: Headers
    ) -> None:
        await client.post("/blogs/sync", headers=api_key_headers, json=self.payload(draft=True))
        await client.post("/blogs/sync", headers=api_key_headers, json=self.payload(draft=False))
        assert (await client.get("/blogs/2026-09-01-a-new-post")).status_code == 200

    async def test_published_cannot_be_set_directly(
        self, client: AsyncClient, api_key_headers: Headers
    ) -> None:
        response = await client.post(
            "/blogs/sync", headers=api_key_headers, json=self.payload(published=False)
        )
        assert response.status_code == 422

    async def test_a_string_date_is_rejected_where_a_datetime_is_required(
        self, client: AsyncClient, api_key_headers: Headers
    ) -> None:
        response = await client.post(
            "/blogs/sync", headers=api_key_headers, json=self.payload(publishedDate="not a date")
        )
        assert response.status_code == 422


class TestOrdering:
    async def test_newest_first(self, client: AsyncClient, api_key_headers: Headers) -> None:
        await client.post(
            "/blogs/sync",
            headers=api_key_headers,
            json={
                "slug": "2027-01-01-newest",
                "title": "Newest",
                "publishedDate": "2027-01-01T00:00:00Z",
            },
        )
        slugs = [item["slug"] for item in (await client.get("/blogs")).json()["items"]]
        assert slugs[0] == "2027-01-01-newest"
