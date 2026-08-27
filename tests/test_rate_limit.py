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
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import Response

from app.core.rate_limit import (
    RouterAwareSlowAPIMiddleware,
    make_limiter,
    rate_limit_handler,
)


class Body(BaseModel):
    name: str


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

    # A decorated route that validates a body: the shape `/contact` and the
    # comment routes have, and the one where the decorator alone is not enough.
    @decorated.post("/decorated-body")
    @limiter.limit("2/minute")
    async def decorated_body(
        request: Request, response: Response, payload: Body
    ) -> dict[str, bool]:
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


class TestDecoratedRoutes:
    async def test_the_tighter_decorator_limit_is_the_one_that_trips(self) -> None:
        # The decorator's 2/minute and the app default of 3/minute both apply
        # now (see `_exempt_from_default`). A 429 fires as soon as *either* is
        # exceeded, so the tighter one governs and the visible behaviour is the
        # same as when decorated routes were exempted outright.
        transport = ASGITransport(app=build_app())
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            codes = [(await http.get("/decorated")).status_code for _ in range(4)]
        assert codes == [200, 200, 429, 429]


class TestValidationFailuresAreStillLimited:
    """A decorator alone leaves an endpoint open to a flood of invalid requests.

    `@limiter.limit` is checked inside the endpoint, and FastAPI validates the
    request body before calling it — so a malformed body is answered with a 422
    having consumed no budget. While decorated routes were also exempted from
    the middleware, nothing checked them at all: `/contact` and the comment
    routes, the two given the *strictest* limits, were the only endpoints in
    the API with no limit whatsoever on invalid input.
    """

    async def test_a_malformed_body_still_consumes_the_default_limit(self) -> None:
        transport = ASGITransport(app=build_app())
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            codes = [(await http.post("/decorated-body", json={})).status_code for _ in range(6)]

        assert 429 in codes, (
            "A decorated route must still be limited on requests that never reach "
            "the handler, or it is the least protected endpoint in the API."
        )
        # The default limit (3/minute), since the decorator never ran.
        assert codes[:3] == [422, 422, 422]

    async def test_a_valid_body_is_limited_by_the_decorator(self) -> None:
        transport = ASGITransport(app=build_app())
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            codes = [
                (await http.post("/decorated-body", json={"name": "a"})).status_code
                for _ in range(4)
            ]
        assert codes == [200, 200, 429, 429]


class TestSlowapiInternals:
    def test_the_names_this_leans_on_still_exist(self) -> None:
        """`RouterAwareSlowAPIMiddleware` reuses three unexported slowapi names.

        If a slowapi upgrade moves any of them the middleware would silently
        stop exempting `@limiter.exempt` routes, or stop checking at all. Fail
        here instead.
        """
        import slowapi.middleware as middleware

        assert callable(middleware._get_route_name)
        assert callable(middleware.async_check_limits)
        assert hasattr(make_limiter("1/minute"), "_exempt_routes")

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
