"""Projects — net-new, so there is no v1 behaviour to preserve."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import users_seed
from tests.types import Headers


def project_doc(slug: str, **overrides: Any) -> dict[str, Any]:
    return {
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "tagline": "One line.",
        "status": "active",
        "stack": ["python"],
        "categories": ["web"],
        "tags": ["api"],
        "featured": False,
        "order": 0,
        "published": True,
        **overrides,
    }


@pytest.fixture
def seed() -> dict[str, list[dict[str, Any]]]:
    return {
        "users": users_seed(),
        "projects": [
            project_doc("api-dileepa-dev", featured=True, order=10, tags=["api", "fastapi"]),
            project_doc("links-dileepa-dev", status="maintained", order=5, categories=["site"]),
            project_doc("old-thing", status="archived", order=1),
            project_doc("draft-thing", published=False),
        ],
    }


class TestListing:
    async def test_featured_first_then_priority(self, client: AsyncClient) -> None:
        slugs = [item["slug"] for item in (await client.get("/projects")).json()["items"]]
        assert slugs == ["api-dileepa-dev", "links-dileepa-dev", "old-thing"]

    async def test_unpublished_is_hidden(self, client: AsyncClient) -> None:
        assert (await client.get("/projects")).json()["total"] == 3

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("featured=true", ["api-dileepa-dev"]),
            ("status=archived", ["old-thing"]),
            ("tag=fastapi", ["api-dileepa-dev"]),
            ("category=site", ["links-dileepa-dev"]),
        ],
    )
    async def test_filters(self, client: AsyncClient, query: str, expected: list[str]) -> None:
        body = (await client.get(f"/projects?{query}")).json()
        assert [item["slug"] for item in body["items"]] == expected

    async def test_an_invalid_status_is_a_422(self, client: AsyncClient) -> None:
        assert (await client.get("/projects?status=abandoned")).status_code == 422


class TestRecords:
    async def test_by_slug(self, client: AsyncClient) -> None:
        body = (await client.get("/projects/api-dileepa-dev")).json()
        assert body["name"] == "Api Dileepa Dev"
        assert body["links"] == {
            "repo": None,
            "demo": None,
            "docs": None,
            "caseStudy": None,
            "package": None,
        }

    async def test_create_with_the_full_model(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post(
            "/projects",
            headers=admin_headers,
            json={
                "slug": "dileepa-dev",
                "name": "dileepa.dev",
                "tagline": "The main website.",
                "description": "# Markdown\n\nBody.",
                "status": "active",
                "role": "Author",
                "period": {"start": "2024-01-01T00:00:00Z"},
                "stack": ["next.js", "tailwind"],
                "links": {"repo": "https://github.com/dileepadev/dileepa-dev"},
                "cover": {"url": "https://res.cloudinary.com/x/c.png", "alt": "Cover"},
                "gallery": [{"url": "https://res.cloudinary.com/x/g.png", "order": 1}],
                "highlights": ["Rebuilt in v2.0.0"],
                "metrics": [{"label": "Lighthouse", "value": "98"}],
                "featured": True,
                "seo": {"metaTitle": "dileepa.dev"},
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["metrics"] == [{"label": "Lighthouse", "value": "98"}]
        assert body["seo"]["metaTitle"] == "dileepa.dev"
        assert body["period"]["end"] is None

    async def test_a_duplicate_slug_is_a_409(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post(
            "/projects", headers=admin_headers, json={"slug": "old-thing", "name": "Clash"}
        )
        assert response.status_code == 409
        assert response.json()["error"]["details"] == {"field": "slug"}

    async def test_writes_need_admin(self, client: AsyncClient, editor_headers: Headers) -> None:
        response = await client.post(
            "/projects", headers=editor_headers, json={"slug": "x", "name": "X"}
        )
        assert response.status_code == 403
