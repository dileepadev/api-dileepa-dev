"""Rate limiting, and the security headers that replace Helmet."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from typing import Any

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware, _should_exempt, async_check_limits
from slowapi.util import get_remote_address
from starlette.middleware.base import RequestResponseEndpoint
from starlette.routing import BaseRoute, Match

from app.core.config import get_settings
from app.core.errors import error_body

settings = get_settings()


def make_limiter(*default_limits: str) -> Limiter:
    """Build a limiter configured the way this API needs one.

    A factory rather than a literal so the test suite can build a limiter with
    small limits that is otherwise *identical* to the real one. Configured two
    different ways, a test proves nothing about production.
    """
    return Limiter(
        key_func=get_remote_address,
        default_limits=list(default_limits),
        headers_enabled=True,
        # Bucket the default limit by handler, not by URL. slowapi's default is
        # `url`, which gives every distinct path its own budget — so
        # `/events/a`, `/events/b` and so on each get the full allowance,
        # and the limit on any route with a parameter is bypassed by varying
        # the parameter. `endpoint` makes RATE_LIMIT_DEFAULT mean what it reads
        # as: this many requests per address, per endpoint, per window.
        key_style="endpoint",
    )


limiter = make_limiter(settings.rate_limit_default)


def _flatten(routes: list[BaseRoute]) -> Iterator[BaseRoute]:
    """Yield real routes, descending into the routers FastAPI keeps nested.

    An `_IncludedRouter` carries the router it wrapped on `.original_router`.
    The routes inside it keep their full path — `/auth/login`, not `/login` —
    so matching against them directly is equivalent to what the app does.
    """
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is None:
            yield route
        else:
            yield from _flatten(nested.routes)


def _resolve_handler(app: Any, scope: Any) -> Callable[..., Any] | None:
    handler = None
    for route in _flatten(app.routes):
        match, _ = route.matches(scope)
        if match == Match.FULL and hasattr(route, "endpoint"):
            handler = route.endpoint
    return handler


class RouterAwareSlowAPIMiddleware(SlowAPIMiddleware):
    """`SlowAPIMiddleware`, but able to find the handler.

    slowapi resolves the endpoint by walking `app.routes` and reading
    `.endpoint` off whatever matches at the top level. Since FastAPI 0.141,
    `include_router` keeps each router nested as an `_IncludedRouter` instead of
    flattening its routes into the app — and an `_IncludedRouter` has no
    `.endpoint`. slowapi therefore finds no handler, concludes the request is
    exempt, and applies the default limit to nothing that was registered through
    a router: which is every endpoint here except the docs, `/auth/login`
    included. It fails open and silently, with no 429 and no `X-RateLimit-*`
    headers to notice.

    Descending into the nested routers restores the lookup. Per-route
    `@limiter.limit` decorators were never affected — they check inside the
    endpoint rather than in the middleware — which is exactly why `/contact`
    kept limiting correctly and hid this for so long.

    This leans on two names slowapi does not export. That is deliberate: reusing
    its exemption and check logic keeps decorated routes behaving identically,
    and only the handler lookup is ours. `tests/test_rate_limit.py` fails if
    either name moves.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        app = request.app
        limiter: Limiter = app.state.limiter
        if not limiter.enabled:
            return await call_next(request)

        handler = _resolve_handler(app, request.scope)
        # Still slowapi's rule: a route carrying its own decorator is left to
        # that decorator, so a limit is never applied twice.
        if _should_exempt(limiter, handler):
            return await call_next(request)

        # async, not slowapi's sync variant: `sync_check_limits` cannot await an
        # async exception handler and silently falls back to slowapi's own,
        # which returns `{"error": "Rate limit exceeded: ..."}`. Every error in
        # this API is `{ error: { code, message, details } }`, and a 429 from
        # the middleware must not be the one exception to that.
        error_response, inject_headers = await async_check_limits(limiter, request, handler, app)
        if error_response is not None:
            return error_response

        response = await call_next(request)
        if inject_headers:
            response = limiter._inject_headers(response, request.state.view_rate_limit)
        return response


async def rate_limit_handler(request: Request, _: Exception) -> Response:
    from fastapi.responses import JSONResponse

    response: Response = JSONResponse(
        status_code=429,
        content=error_body(
            "rate_limited",
            "Too many requests from this address. Wait a moment and try again.",
        ),
    )

    # slowapi records the limit that failed on the request before raising, on
    # both the middleware and the decorator path, so reusing its own injection
    # here covers both. Without it the 429 was the *only* response with no
    # rate-limit headers — including no `Retry-After`, on the one response
    # where a client actually needs to be told how long to back off for.
    view_rate_limit = getattr(request.state, "view_rate_limit", None)
    limiter_for_app = getattr(request.app.state, "limiter", None)
    if view_rate_limit is not None and limiter_for_app is not None:
        response = limiter_for_app._inject_headers(response, view_rate_limit)
    return response


# Helmet's defaults, minus the ones that only apply to HTML responses. This API
# serves JSON, so a restrictive CSP plus nosniff and frame denial is the whole
# useful surface.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "accelerometer=(), camera=(), geolocation=(), microphone=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

# This API serves JSON, so it needs nothing at all: no scripts, no styles, no
# frames.
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


def _docs_csp() -> str:
    """The reference page's policy, which is narrower than "no policy".

    Scalar loads its bundle from a CDN, so the strict API policy blanks the
    page. Exempting the path entirely would be the easy fix and the wrong one:
    this allows exactly that origin and nothing else. `unsafe-inline` is
    required because Scalar's loader is an inline script.
    """
    cdn = settings.scalar_cdn_origin
    return (
        "default-src 'none'; "
        f"script-src 'self' 'unsafe-inline' {cdn}; "
        f"style-src 'self' 'unsafe-inline' {cdn}; "
        f"font-src 'self' data: {cdn}; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'"
    )


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    is_docs = request.url.path == settings.docs_path
    response.headers.setdefault("Content-Security-Policy", _docs_csp() if is_docs else _API_CSP)
    return response
