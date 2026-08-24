"""The API reference, the root endpoint, and what production does not serve.

Scalar renders the reference at `/docs`, replacing Swagger UI and ReDoc. The v1
posture is unchanged: docs are enabled in development and **disabled in
production**, which for Scalar means the page and the spec it reads both have
to disappear, not just the page.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def production_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    yield create_app()
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()


@pytest.fixture
async def production_client(production_app: Any) -> Any:
    transport = ASGITransport(app=production_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


class TestRoot:
    async def test_says_what_the_service_is(self, client: AsyncClient) -> None:
        response = await client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "api.dileepa.dev"
        assert body["version"] == "2.0.0"
        assert body["website"] == "https://dileepa.dev"

    async def test_points_at_the_docs_in_development(self, client: AsyncClient) -> None:
        assert (await client.get("/")).json()["docs"] == "/docs"

    async def test_advertises_no_docs_in_production(self, production_client: AsyncClient) -> None:
        """A dead link is worse than no link."""
        assert (await production_client.get("/")).json()["docs"] is None

    async def test_is_public(self, client: AsyncClient) -> None:
        # v1 served `GET /` unauthenticated; anything else would break a
        # bookmark for no reason.
        assert (await client.get("/")).status_code == 200


class TestReference:
    async def test_is_served_in_development(self, client: AsyncClient) -> None:
        response = await client.get("/docs")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

    async def test_loads_scalar_and_points_at_the_spec(self, client: AsyncClient) -> None:
        body = (await client.get("/docs")).text
        assert "@scalar/api-reference" in body
        assert "/api-json" in body

    async def test_the_spec_is_served_in_development(self, client: AsyncClient) -> None:
        response = await client.get("/api-json")
        assert response.status_code == 200
        assert response.json()["info"]["title"] == "api.dileepa.dev"

    async def test_is_not_served_in_production(self, production_client: AsyncClient) -> None:
        assert (await production_client.get("/docs")).status_code == 404

    async def test_the_spec_is_not_served_in_production(
        self, production_client: AsyncClient
    ) -> None:
        """The page going away is not enough if the spec it reads is still up."""
        assert (await production_client.get("/api-json")).status_code == 404

    async def test_swagger_ui_and_redoc_are_gone(self, client: AsyncClient) -> None:
        # Replaced by Scalar. The old paths should not linger as dead routes.
        assert (await client.get("/api")).status_code == 404
        assert (await client.get("/api/redoc")).status_code == 404

    async def test_is_not_in_the_schema(self, client: AsyncClient) -> None:
        spec = (await client.get("/api-json")).json()
        assert "/docs" not in spec["paths"]


class TestContentSecurityPolicy:
    async def test_the_api_allows_nothing(self, client: AsyncClient) -> None:
        policy = (await client.get("/version")).headers["Content-Security-Policy"]
        assert policy.startswith("default-src 'none'")
        assert "cdn.jsdelivr.net" not in policy

    async def test_the_reference_may_load_its_bundle(self, client: AsyncClient) -> None:
        """Without this the page renders blank: the strict policy blocks Scalar."""
        policy = (await client.get("/docs")).headers["Content-Security-Policy"]
        assert "script-src" in policy
        assert "https://cdn.jsdelivr.net" in policy

    async def test_the_reference_policy_is_still_narrow(self, client: AsyncClient) -> None:
        """Allowing one origin, not exempting the path from CSP altogether."""
        policy = (await client.get("/docs")).headers["Content-Security-Policy"]
        assert policy.startswith("default-src 'none'")
        assert "frame-ancestors 'none'" in policy
        assert "connect-src 'self'" in policy
