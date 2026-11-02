"""`GET /stats` — public counts that never include a draft or a hidden comment."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


@pytest.fixture
def seed(seed: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {
        **seed,
        "blogs": [
            {"slug": "a", "title": "A"},
            {"slug": "b", "title": "B", "published": True},
            {"slug": "c", "title": "C", "published": False},
        ],
        "projects": [{"slug": "p", "title": "P"}, {"slug": "q", "title": "Q", "published": False}],
        "events": [{"slug": "e", "title": "E"}],
        "videos": [{"title": "V"}, {"title": "W", "published": False}],
        "tools": [{"title": "T"}],
        "comments": [{"published": True}, {"published": False}, {}],
    }


class TestStats:
    async def test_it_is_public_and_counts_only_what_is_published(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["blogs"] == 2
        assert body["projects"] == 1
        assert body["events"] == 1
        assert body["videos"] == 1
        assert body["tools"] == 1
        assert body["comments"] == 2
        assert body["experiences"] == 0
        assert body["speakingTopics"] == 0
        assert "generatedAt" in body

    async def test_it_may_be_cached_for_a_minute(self, client: AsyncClient) -> None:
        response = await client.get("/stats")
        assert response.headers["cache-control"] == "public, max-age=60"

    async def test_it_needs_no_token_in_the_spec(self, client: AsyncClient) -> None:
        spec = (await client.get("/api-json")).json()
        assert "security" not in spec["paths"]["/stats"]["get"]
