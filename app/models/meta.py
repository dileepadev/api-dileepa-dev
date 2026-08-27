"""Service metadata — `/health`, `/version`, and the admin's `/status`."""

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


class SystemStatus(ApiModel):
    """What the admin dashboard's header shows: where this session is pointed.

    Admin-only and unrelated to `/maintenance/*` — this is read-only, tells a
    signed-in session which deployment it is actually talking to, and is
    registered in every environment rather than only outside production. A
    session pointed at `api.dileepa.dev` should see "production" here just as
    plainly as one pointed at a local API sees "development".

    `database` is the credential-free label — see `database_label` in
    `app/core/config.py`. Nothing that reaches this model can be used to open a
    connection.
    """

    environment: str
    version: str
    database: str
    docs_enabled: bool
    #: Whether `/maintenance/*` is registered on *this* deployment. `main.py`
    #: does not include that router in production, so this is false there and
    #: the admin can say so rather than offering a Database screen that 404s.
    maintenance_available: bool
