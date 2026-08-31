"""Test fixtures.

Every test runs against `InMemoryRepository`, so the suite needs no MongoDB, no
network and no API keys — `AGENTS.md`: "Keep tests offline."

The app under test is the real one. Only the repository providers and the two
external services (Resend, Cloudinary) are swapped out, so routing, validation,
auth, serialisation and the error envelope are all genuinely exercised.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

# Set before the app imports, so `get_settings()` picks these up.
#
# `DOTENV_DISABLED` stops any dotenv file being read. Without it a developer's
# own `.env.development` would supply every value this block does not name — a
# real Resend key, a real cluster — and the suite would stop being offline on
# exactly the machine where that matters.
os.environ.update(
    DOTENV_DISABLED="1",
    ENVIRONMENT="development",
    MONGODB_URI="mongodb://localhost:27017/test",
    JWT_SECRET="test-secret-not-a-real-one",
    BLOG_SYNC_API_KEY="test-api-key",
    SITE_URL="https://dileepa.dev",
    CORS_ORIGINS="https://dileepa.dev",
    RATE_LIMIT_DEFAULT="10000/minute",
    RATE_LIMIT_CONTACT="10000/minute",
    RATE_LIMIT_COMMENT="10000/minute",
)

from app.core.config import get_settings
from app.core.deps import repository
from app.core.security import ACCESS, REFRESH, create_token, hash_password
from app.main import create_app
from app.repositories.memory import InMemoryRepository

# A real hash produced by Node's `bcrypt` at cost 10 for the password below.
# Verifying it here is the migration's load-bearing assertion: if `pwdlib` ever
# stops reading Node's output, this fails before anyone is locked out.
NODE_BCRYPT_HASH = "$2b$10$QSoc.NecICc/0GuqmMb8w.3JXa99EtxrCGtodCl533pcPmNTsazAS"
NODE_BCRYPT_PASSWORD = "S0me-Real!Password_2026"

ADMIN_ID = ObjectId()
EDITOR_ID = ObjectId()

# Hashed once for the whole event. argon2id is deliberately slow, and hashing
# these per test added most of a minute to the suite.
EDITOR_HASH = hash_password("editor-password")
DISABLED_HASH = hash_password("disabled-password")

COLLECTIONS = (
    "about",
    "experiences",
    "educations",
    "tools",
    "communities",
    "videos",
    "pillars",
    "speaking_topics",
    "blogs",
    "events",
    "projects",
    "uploads",
    "users",
    "blog_views",
    "blog_reactions",
    "comments",
    "comment_reactions",
    "contacts",
)

UNIQUE_FIELDS: dict[str, tuple[str, ...]] = {
    "blogs": ("slug",),
    # The view de-duplication *is* this index. Without it here the in-memory
    # repository would happily record the same reader twice and the dedup test
    # would pass against a database that does not behave that way.
    "blog_views": ("key",),
    "events": ("slug",),
    "projects": ("slug",),
    "tools": ("name",),
    "uploads": ("publicId",),
    "users": ("email",),
}


def users_seed() -> list[dict[str, Any]]:
    return [
        {
            "_id": ADMIN_ID,
            "email": "owner@dileepa.dev",
            # Stored exactly as the NestJS app wrote it.
            "passwordHash": NODE_BCRYPT_HASH,
            "roles": ["admin"],
            "isActive": True,
        },
        {
            "_id": EDITOR_ID,
            "email": "editor@dileepa.dev",
            "passwordHash": EDITOR_HASH,
            "roles": ["user"],
            "isActive": True,
        },
        {
            "_id": ObjectId(),
            "email": "disabled@dileepa.dev",
            "passwordHash": DISABLED_HASH,
            "roles": ["admin"],
            "isActive": False,
        },
    ]


@pytest.fixture
def seed() -> dict[str, list[dict[str, Any]]]:
    """Per-collection seed data. Override in a test to change what is stored."""
    return {"users": users_seed()}


@pytest.fixture
def repositories(seed: dict[str, list[dict[str, Any]]]) -> dict[str, InMemoryRepository]:
    return {
        name: InMemoryRepository(
            seed.get(name, []), label=name.rstrip("s"), unique=UNIQUE_FIELDS.get(name, ())
        )
        for name in COLLECTIONS
    }


def _provider(repo: InMemoryRepository) -> Callable[[], InMemoryRepository]:
    """Return the repository itself, every time.

    This must take no parameters. A `lambda repo=repo: repo` reads as
    equivalent, but FastAPI treats `repo` as a request parameter and Pydantic
    deep-copies its default, so each request would get its own copy of the
    repository and every write would be silently discarded.
    """

    def provide() -> InMemoryRepository:
        return repo

    return provide


@pytest.fixture
def app(repositories: dict[str, InMemoryRepository]) -> Iterator[Any]:
    get_settings.cache_clear()
    application = create_app()
    for name, repo in repositories.items():
        application.dependency_overrides[repository(name)] = _provider(repo)
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    # ASGITransport calls the app directly: no socket, no server, no lifespan,
    # so no attempt is made to reach MongoDB.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


def token_for(user_id: ObjectId, email: str, roles: list[str], *, token_type: str = ACCESS) -> str:
    settings = get_settings()
    return create_token(
        settings,
        subject=str(user_id),
        email=email,
        roles=roles,
        token_type=token_type,  # type: ignore[arg-type]
    )


@pytest.fixture
def admin_token() -> str:
    return token_for(ADMIN_ID, "owner@dileepa.dev", ["admin"])


@pytest.fixture
def editor_token() -> str:
    return token_for(EDITOR_ID, "editor@dileepa.dev", ["user"])


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def editor_headers(editor_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {editor_token}"}


@pytest.fixture
def api_key_headers() -> dict[str, str]:
    return {"x-api-key": "test-api-key"}


@pytest.fixture
def refresh_token() -> str:
    return token_for(ADMIN_ID, "owner@dileepa.dev", ["admin"], token_type=REFRESH)


def expired_token(email: str = "owner@dileepa.dev") -> str:
    settings = get_settings()
    return create_token(
        settings,
        subject=str(ADMIN_ID),
        email=email,
        roles=["admin"],
        token_type=ACCESS,
        expires_delta=timedelta(seconds=-60),
    )


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
