"""Rate limiting, and the security headers that replace Helmet."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.errors import error_body

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    headers_enabled=True,
)


async def rate_limit_handler(_: Request, exc: Exception) -> Response:
    from fastapi.responses import JSONResponse

    retry_after = getattr(exc, "retry_after", None)
    response = JSONResponse(
        status_code=429,
        content=error_body(
            "rate_limited",
            "Too many requests from this address. Wait a moment and try again.",
        ),
    )
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
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

# The docs pages need to load their own scripts and styles, so the strict policy
# is applied everywhere except there.
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
_DOCS_PATHS = ("/api", "/api-json")


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if not request.url.path.startswith(_DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", _API_CSP)
    return response
