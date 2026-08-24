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
