"""Dependencies: who is calling, and what they are allowed to touch.

Only this module and `app.core.security` know about tokens. Nothing downstream
parses a JWT.

The v1 posture is kept: endpoints are protected by default in the sense that
every write requires the `admin` role, and reads that were public stay public.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.db import mongo
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.models.auth import AuthenticatedUser
from app.repositories.base import DocumentRepository, MongoRepository

SettingsDep = Annotated[Settings, Depends(get_settings)]

# auto_error=False so a missing header raises this API's error envelope rather
# than Starlette's `{"detail": ...}`.
_bearer = HTTPBearer(auto_error=False, scheme_name="JWT-auth", description="Enter a JWT token")

BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]

# Label used in conflict messages, and the fields Mongo enforces as unique.
_REPOSITORY_SPEC: dict[str, tuple[str, tuple[str, ...]]] = {
    "about": ("about record", ()),
    "experiences": ("experience", ()),
    "educations": ("education", ()),
    "tools": ("tool", ("name",)),
    "communities": ("community", ()),
    "videos": ("video", ()),
    "blogs": ("blog post", ("slug",)),
    "events": ("event", ("slug",)),
    "projects": ("project", ("slug",)),
    "uploads": ("upload", ("publicId",)),
    "users": ("user", ("email",)),
    "blog_views": ("blog view", ("key",)),
    "blog_reactions": ("blog reaction", ()),
    "comments": ("comment", ()),
    "comment_reactions": ("comment reaction", ()),
}


@lru_cache
def repository(name: str) -> Callable[[], DocumentRepository]:
    """Provide a repository for a collection.

    Cached so every route that reads the same collection shares one provider
    object. That is what makes `app.dependency_overrides[repository("blogs")]`
    reach every route, which is how the tests swap in an `InMemoryRepository`
    and run the whole suite without a database.
    """
    label = _REPOSITORY_SPEC.get(name, (name.rstrip("s"), ()))[0]

    def provide() -> DocumentRepository:
        return MongoRepository(mongo.collection(name), label=label)

    provide.__name__ = f"provide_{name}_repository"
    return provide


async def optional_user(
    credentials: BearerDep,
    settings: SettingsDep,
) -> AuthenticatedUser | None:
    """The caller, when they presented a valid token. `None` otherwise.

    Used by endpoints that are public but show more to an authenticated admin —
    unpublished records, for instance.
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = decode_token(settings, credentials.credentials, expected_type="access")
    except UnauthorizedError:
        # A bad token on a public endpoint is the same as no token.
        return None
    return AuthenticatedUser(
        user_id=str(payload["sub"]),
        email=str(payload.get("email", "")),
        roles=list(payload.get("roles", [])),
    )


async def current_user(
    credentials: BearerDep,
    settings: SettingsDep,
) -> AuthenticatedUser:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError(
            "This endpoint needs a bearer token. Sign in first.",
            code="missing_token",
        )
    payload = decode_token(settings, credentials.credentials, expected_type="access")
    return AuthenticatedUser(
        user_id=str(payload["sub"]),
        email=str(payload.get("email", "")),
        roles=list(payload.get("roles", [])),
    )


CurrentUser = Annotated[AuthenticatedUser, Depends(current_user)]
OptionalUser = Annotated[AuthenticatedUser | None, Depends(optional_user)]


def require_roles(*roles: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Mirror of v1's `@Roles(...)` guard."""

    def guard(user: CurrentUser) -> AuthenticatedUser:
        if not user.has_role(*roles):
            raise ForbiddenError(
                f"This endpoint needs the {' or '.join(roles)} role.",
                code="insufficient_role",
            )
        return user

    return guard


require_admin = require_roles("admin")
AdminUser = Annotated[AuthenticatedUser, Depends(require_admin)]


async def require_api_key(request: Request, settings: SettingsDep) -> None:
    """Machine-to-machine auth for the blog pipeline.

    Same header as v1 (`x-api-key`) and the same environment variable, so the
    blog repo's workflow needs no change at cutover.
    """
    provided = request.headers.get("x-api-key")
    if not provided:
        raise UnauthorizedError("Send the API key in an x-api-key header.", code="missing_api_key")
    expected = settings.blog_sync_api_key
    if not expected:
        raise UnauthorizedError(
            "No API key is configured on the server, so this endpoint is closed.",
            code="api_key_not_configured",
        )
    if not secrets.compare_digest(provided, expected):
        raise UnauthorizedError("That API key is not valid.", code="invalid_api_key")


ApiKeyGuard = Depends(require_api_key)


async def api_key_or_admin(
    request: Request,
    settings: SettingsDep,
    user: OptionalUser,
) -> None:
    """`POST /uploads` accepts either an admin JWT or the pipeline's API key."""
    if user is not None and user.has_role("admin"):
        return
    if request.headers.get("x-api-key"):
        await require_api_key(request, settings)
        return
    raise UnauthorizedError(
        "This endpoint needs an admin token or an x-api-key header.",
        code="missing_credentials",
    )
