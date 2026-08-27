"""Service metadata, the root, and the API reference.

`GET /health` and `GET /version` are new in v2.0.0. `GET /` carries over from
v1, where it returned the string `Hello World!`; it now returns something a
person landing on the bare domain can act on.

`GET /status` is admin-only and answers a different question than `/version`:
not "what build is this" but "which deployment is this session actually
driving". The admin dashboard reads it for the header, so a signed-in session
pointed at `api.dileepa.dev` cannot be mistaken for one pointed at a laptop —
unlike `/maintenance/*`, this route is registered in every environment.

The reference is rendered by **Scalar** at `/docs`, replacing Swagger UI and
ReDoc. It is registered only when docs are enabled, so production serves
neither the page nor the spec it reads — the v1 posture, kept.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import APIRouter, Response, status
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from app.core.config import get_settings
from app.core.db import mongo
from app.core.deps import AdminUser
from app.core.scalar_theme import BRAND_CSS
from app.models.meta import Health, HealthChecks, ServiceInfo, SystemStatus, Version

router = APIRouter(tags=["meta"])


@lru_cache
def app_version() -> str:
    """The version in `pyproject.toml`, which is the single source of truth.

    A deployed install reads it from package metadata. Running from a checkout
    there is no metadata, so the file itself is read — otherwise `/version`
    reports 0.0.0 in development and nobody notices until it does so in
    production too.
    """
    try:
        return version("api-dileepa-dev")
    except PackageNotFoundError:
        pass
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        with pyproject.open("rb") as handle:
            return str(tomllib.load(handle)["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError):  # pragma: no cover
        return "0.0.0"


@router.get("/", response_model=ServiceInfo, summary="What this service is")
async def root() -> ServiceInfo:
    """Point a person who landed on the bare domain at something useful."""
    settings = get_settings()
    return ServiceInfo(
        name="api.dileepa.dev",
        version=app_version(),
        # Null rather than a dead link when docs are off, so production does
        # not advertise a page it refuses to serve.
        docs=settings.docs_path if settings.serve_docs else None,
        website="https://dileepa.dev",
    )


@router.get("/health", response_model=Health, summary="Liveness and database reachability")
async def health(response: Response) -> Health:
    """Report whether the API can reach MongoDB.

    Returns 503 when the database is unreachable, so an uptime check does not
    have to parse the body to notice.
    """
    database_up = await mongo.ping()
    if not database_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Health(
        status="ok" if database_up else "degraded",
        checks=HealthChecks(database="up" if database_up else "down"),
    )


@router.get("/version", response_model=Version, summary="Build and runtime information")
async def read_version() -> Version:
    settings = get_settings()
    return Version(
        name="api.dileepa.dev",
        version=app_version(),
        environment=settings.environment,
        framework="fastapi",
    )


@router.get(
    "/status",
    response_model=SystemStatus,
    summary="Which deployment this admin session is pointed at",
)
async def system_status(_: AdminUser) -> SystemStatus:
    """Environment, version, and database — with credentials stripped.

    `/version` answers the same "which environment" question but is public and
    therefore deliberately thin. This carries the one field `/version` cannot:
    `database`, which is fine to show a signed-in admin and not fine to hand
    an anonymous caller for free, since it names the Atlas cluster.
    """
    settings = get_settings()
    return SystemStatus(
        environment=settings.environment,
        version=app_version(),
        database=settings.database_label,
        docs_enabled=settings.serve_docs,
        maintenance_available=not settings.is_production,
    )


async def scalar_reference() -> HTMLResponse:
    """The API reference.

    Registered by `create_app` only when docs are enabled, which is why it is a
    bare handler rather than a decorated route: a route that must not exist in
    production should not be declared at import time.
    """
    settings = get_settings()
    return get_scalar_api_reference(
        openapi_url=settings.openapi_url or "/api-json",
        title="api.dileepa.dev",
        scalar_js_url=settings.scalar_js_url,
        scalar_favicon_url=f"{settings.site_url.rstrip('/')}/favicon.ico",
        dark_mode=True,
        # No usage data leaves this deployment because someone opened the docs.
        telemetry=False,
        # Scalar's defaults are Inter and JetBrains Mono. The brand permits
        # Manrope and JetBrains Mono and no third family, so the default pair
        # is turned off and the theme loads the right two itself.
        with_default_fonts=False,
        custom_css=BRAND_CSS,
    )
