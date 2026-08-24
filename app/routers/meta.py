"""Service metadata. Both endpoints are new in v2.0.0."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.db import mongo
from app.models.meta import Health, HealthChecks, Version

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
