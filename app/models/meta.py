"""Service metadata — `/health` and `/version`."""

from __future__ import annotations

from typing import Literal

from app.models.common import ApiModel


class HealthChecks(ApiModel):
    database: Literal["up", "down"]


class Health(ApiModel):
    status: Literal["ok", "degraded"]
    checks: HealthChecks


class ServiceInfo(ApiModel):
    """What `GET /` returns."""

    name: str
    version: str
    docs: str | None = None
    website: str


class Version(ApiModel):
    name: str
    version: str
    environment: str
    framework: str
