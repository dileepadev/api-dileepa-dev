"""api.dileepa.dev — the FastAPI application.

Run it through the FastAPI CLI, not uvicorn directly:

    uv run fastapi dev      # development, with reload
    uv run fastapi run      # serve

The API reference is served at `/docs`, rendered by Scalar, and the OpenAPI
JSON at `/api-json`. Both are enabled in development and **disabled in
production**. That is the v1 posture, deliberately kept.

`ENVIRONMENT` names the single dotenv file that loads — see `app/core/config.py`.
A production deployment that is misconfigured refuses to start, below, rather
than serving traffic with development's database or a placeholder secret.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.core.config import Settings, env_file, get_settings
from app.core.db import mongo
from app.core.errors import register_exception_handlers
from app.core.rate_limit import (
    RouterAwareSlowAPIMiddleware,
    limiter,
    rate_limit_handler,
    security_headers_middleware,
)
from app.routers import (
    about,
    api_links,
    auth,
    blogs,
    contact,
    events,
    meta,
    profile,
    projects,
)
from app.routers import uploads as uploads_router
from app.routers.meta import app_version

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

DESCRIPTION = """
The data source for [dileepa.dev](https://dileepa.dev), its admin dashboard, and
the blog sync pipeline.

Collection endpoints return `{ "items": [...], "total": n, "limit": n, "offset": n }`.
Errors return `{ "error": { "code": "...", "message": "...", "details": null } }`.
Public callers see published records only; an admin token sees everything.
""".strip()

TAGS_METADATA = [
    {"name": "meta", "description": "Health and version."},
    {"name": "auth", "description": "Sign in, refresh, and the current user."},
    {"name": "about", "description": "The single about record."},
    {"name": "experiences", "description": "Work history."},
    {"name": "educations", "description": "Education history."},
    {"name": "tools", "description": "Tools and technologies."},
    {"name": "communities", "description": "Community involvement."},
    {"name": "videos", "description": "Video appearances."},
    {"name": "projects", "description": "Projects. New in v2.0.0."},
    {
        "name": "events",
        "description": "Talks, workshops and webinars. Reshaped in v2.0.0.",
    },
    {"name": "blogs", "description": "Blog post metadata, and the sync pipeline."},
    {"name": "contact", "description": "The contact form."},
    {"name": "uploads", "description": "Cloudinary-backed image uploads."},
    {
        "name": "api-links",
        "description": (
            "The API's own endpoint catalogue, for the admin dashboard. Admin only, "
            "and not read by the public website."
        ),
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # Checked before the database is opened, so a production deploy carrying
    # development's configuration fails without ever connecting to whatever it
    # was pointed at. Startup is the right place for this: it is the only moment
    # the whole configuration is known and nothing has happened yet.
    problems = settings.production_problems()
    if problems:
        raise RuntimeError(
            "Refusing to start in production with this configuration:\n  - "
            + "\n  - ".join(problems)
        )
    for warning in settings.production_warnings():
        logger.warning("%s", warning)

    # Outside production a missing file means the developer has not made one
    # yet, and every value below is a field default — including a localhost
    # database. Saying so beats letting them wonder why the data looks empty.
    expected = env_file()
    if expected is not None and not expected.exists() and not settings.is_production:
        logger.warning(
            "No %s found, so configuration is coming from defaults and the "
            "process environment. Copy %s.example to it.",
            expected,
            expected,
        )

    await mongo.connect(settings)
    await mongo.ensure_indexes()
    logger.info(
        "api.dileepa.dev started in %s against %s; docs %s",
        settings.environment,
        settings.database_label,
        f"enabled at {settings.docs_path}" if settings.serve_docs else "disabled",
    )
    try:
        yield
    finally:
        await mongo.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="api.dileepa.dev",
        description=DESCRIPTION,
        version=app_version(),
        openapi_tags=TAGS_METADATA,
        contact={
            "name": "Dileepa Bandara",
            "url": "https://dileepa.dev",
            "email": "contact@dileepa.dev",
        },
        license_info={
            "name": "MIT",
            "url": "https://github.com/dileepadev/api-dileepa-dev/blob/main/LICENSE",
        },
        # Swagger UI and ReDoc are off: Scalar renders the reference instead,
        # registered below and only when docs are enabled.
        docs_url=None,
        redoc_url=None,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    register_exception_handlers(app)

    # Router-aware: stock SlowAPIMiddleware cannot see endpoints registered
    # through include_router on FastAPI 0.141. See app/core/rate_limit.py.
    app.add_middleware(RouterAwareSlowAPIMiddleware)
    app.middleware("http")(security_headers_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "x-api-key"],
        # Retry-After is the only header a browser client has to read off a
        # cross-origin response: the rate limiter sets it on a 429.
        expose_headers=["Retry-After"],
    )

    # Not declared at import time: a page that must not exist in production
    # should not be a route object that merely happens to be unreachable.
    if settings.serve_docs:
        app.add_api_route(
            settings.docs_path,
            meta.scalar_reference,
            methods=["GET"],
            include_in_schema=False,
        )

    app.include_router(meta.router)
    app.include_router(auth.router)
    app.include_router(about.router)
    app.include_router(profile.experiences_router)
    app.include_router(profile.educations_router)
    app.include_router(profile.tools_router)
    app.include_router(profile.communities_router)
    app.include_router(profile.videos_router)
    app.include_router(projects.router)
    app.include_router(events.router)
    app.include_router(blogs.router)
    app.include_router(contact.router)
    app.include_router(uploads_router.router)
    # Last, because it describes the ones above it. Registration order is the
    # order tags are read in, and a catalogue belongs after its contents.
    app.include_router(api_links.router)

    return app


app = create_app()
