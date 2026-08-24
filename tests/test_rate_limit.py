"""The default rate limit has to apply to endpoints registered through routers.

It did not. slowapi finds a request's handler by walking `app.routes` and
reading `.endpoint` off whatever matches, but since FastAPI 0.141
`include_router` keeps routers nested as `_IncludedRouter` objects, which have
no `.endpoint`. slowapi found nothing, treated every such request as exempt, and
applied `RATE_LIMIT_DEFAULT` to nothing — `/auth/login` included, so there was no
brute-force protection at all. It failed open, with no 429 and no `X-RateLimit-*`
header to give it away.

These build their own small app rather than using the fixture one: the suite
runs with the limits set enormous so they never interfere elsewhere, and what
needs pinning here is the middleware, not this app's numbers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import Response

from app.core.rate_limit import (
    RouterAwareSlowAPIMiddleware,
    make_limiter,
    rate_limit_handler,
)


def build_app(limit: str = "3/minute") -> FastAPI:
    app = FastAPI()
    # The real factory, so this exercises the production configuration.
    limiter = make_limiter(limit)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_middleware(RouterAwareSlowAPIMiddleware)

    # Registered directly on the app: this always worked.
    @app.get("/direct")
    async def direct() -> dict[str, bool]:
        return {"ok": True}

    # Registered through a router, with a prefix: this is what silently escaped.
    router = APIRouter(prefix="/things")

    @router.get("")
    async def list_things() -> dict[str, bool]:
        return {"ok": True}

    @router.get("/{identifier}")
    async def get_thing(identifier: str) -> dict[str, str]:
        return {"id": identifier}

    app.include_router(router)

    # A route with its own decorator must stay the decorator's business, or the
    # limit would be counted twice.
    decorated = APIRouter()

    @decorated.get("/decorated")
    @limiter.limit("2/minute")
    async def decorated_endpoint(request: Request, response: Response) -> dict[str, bool]:
        # slowapi reads the address off `request` and writes its headers
        # onto `response`; both are required even though neither is used.
        return {"ok": True}

    app.include_router(decorated)
    return app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=build_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


class TestRoutedEndpointsAreLimited:
    async def test_a_router_registered_path_is_limited(self, client: AsyncClient) -> None:
        codes = [(await client.get("/things")).status_code for _ in range(5)]
        assert codes == [200, 200, 200, 429, 429]

    async def test_a_router_path_with_a_parameter_is_limited(self, client: AsyncClient) -> None:
        codes = [(await client.get(f"/things/{i}")).status_code for i in range(5)]
        assert codes[-1] == 429

    async def test_a_directly_registered_path_is_still_limited(self, client: AsyncClient) -> None:
        codes = [(await client.get("/direct")).status_code for _ in range(5)]
        assert codes[-1] == 429

    async def test_the_limited_response_uses_the_api_error_envelope(
        self, client: AsyncClient
    ) -> None:
        for _ in range(4):
            response = await client.get("/things")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "rate_limited"

    async def test_rate_limit_headers_are_present(self, client: AsyncClient) -> None:
        # Their absence was the visible symptom, and the quickest way to notice
        # a regression by hand.
        response = await client.get("/things")
        assert any(header.lower().startswith("x-ratelimit") for header in response.headers)

    async def test_the_429_tells_the_caller_when_to_retry(self, client: AsyncClient) -> None:
        # The one response where a client genuinely needs Retry-After was the
        # only one that had no rate-limit headers at all.
        for _ in range(4):
            response = await client.get("/things")
        assert response.status_code == 429
        assert response.headers["Retry-After"]
        assert response.headers["X-RateLimit-Limit"] == "3"

    async def test_a_decorated_route_429_also_carries_them(self, client: AsyncClient) -> None:
        # Different code path: the decorator raises, the middleware does not.
        for _ in range(3):
            response = await client.get("/decorated")
        assert response.status_code == 429
        assert response.headers["Retry-After"]


class TestDecoratedRoutesAreLeftAlone:
    async def test_the_decorator_limit_applies_not_the_default(self) -> None:
        # 2/minute from the decorator, not the app default of 3/minute. If the
        # middleware stopped exempting decorated routes the third request would
        # still be allowed by one of the two limits, and the counts would drift.
        transport = ASGITransport(app=build_app())
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            codes = [(await http.get("/decorated")).status_code for _ in range(4)]
        assert codes == [200, 200, 429, 429]


class TestSlowapiInternals:
    def test_the_names_this_leans_on_still_exist(self) -> None:
        """`RouterAwareSlowAPIMiddleware` reuses two unexported slowapi names.

        If a slowapi upgrade moves either, the middleware would silently stop
        exempting decorated routes or stop checking at all. Fail here instead.
        """
        import slowapi.middleware as middleware

        assert callable(middleware._should_exempt)
        assert callable(middleware.async_check_limits)

    def test_nested_routers_are_still_why_this_is_needed(self) -> None:
        """The moment FastAPI flattens `include_router` again, this is dead code.

        Not a failure — just the signal to delete the middleware and go back to
        the stock one.
        """
        from app.main import app

        nested = [r for r in app.routes if hasattr(r, "original_router")]
        assert nested, (
            "FastAPI no longer nests included routers. RouterAwareSlowAPIMiddleware "
            "may no longer be needed — check whether stock SlowAPIMiddleware limits "
            "a router-registered endpoint, and if it does, delete ours."
        )
