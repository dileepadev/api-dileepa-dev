"""api.dileepa.dev — the FastAPI application.

Run it through the FastAPI CLI, not uvicorn directly:

    uv run fastapi dev      # development, with reload
    uv run fastapi run      # serve

Interactive docs are served at `/api` and the OpenAPI JSON at `/api-json`,
enabled in development and **disabled in production**. That is the v1 posture,
deliberately kept.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import Settings, get_settings
from app.core.db import mongo
from app.core.errors import register_exception_handlers
from app.core.rate_limit import limiter, rate_limit_handler, security_headers_middleware
from app.routers import about, auth, blogs, contact, events, meta, profile, projects, sessions
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
    {"name": "sessions", "description": "Talks, workshops and webinars. New in v2.0.0."},
    {"name": "events", "description": "Deprecated alias over sessions. Removed in v2.1.0."},
    {"name": "blogs", "description": "Blog post metadata, and the sync pipeline."},
    {"name": "contact", "description": "The contact form."},
    {"name": "uploads", "description": "Cloudinary-backed image uploads."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await mongo.connect(settings)
    await mongo.ensure_indexes()
    logger.info(
        "api.dileepa.dev started in %s; docs %s",
        settings.environment,
        "enabled at /api" if settings.serve_docs else "disabled",
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
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    register_exception_handlers(app)

    app.add_middleware(SlowAPIMiddleware)
    app.middleware("http")(security_headers_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "x-api-key"],
        expose_headers=["Deprecation", "Sunset", "Link", "Retry-After"],
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
    app.include_router(sessions.router)
    app.include_router(events.router)
    app.include_router(blogs.router)
    app.include_router(contact.router)
    app.include_router(uploads_router.router)

    return app


app = create_app()
