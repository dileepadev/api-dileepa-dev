"""Deprecation headers for the two v1 paths that survive into v2.0.0.

`GET /events` and `POST /auth/sign-in` both exist so nothing breaks mid-migration.
Both are removed in v2.1.0, not before, and only once no consumer calls them.
"""

from __future__ import annotations

from fastapi import Response

# Announced removal date. Twelve months past the v2.0.0 cutover, which is the
# same window the blog redirect layer is held open for.
SUNSET = "Wed, 30 Jun 2027 23:59:59 GMT"


def mark_deprecated(response: Response, successor: str) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = SUNSET
    response.headers["Link"] = f'<{successor}>; rel="successor-version"'
