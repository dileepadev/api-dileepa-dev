"""Shapes for the development-only database maintenance routes.

These exist so a developer can work against real content without touching it:
`POST /maintenance/database/copy` replaces the development database's contents
with a copy of production's, and `POST /maintenance/database/clear` empties it.

Neither is served in production — `app/main.py` does not register the router
there. See `app/routers/maintenance.py` for the rest of the guards.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.common import ApiModel

MaintenanceAction = Literal["copy", "clear"]


class CollectionCount(ApiModel):
    """How many documents a collection holds on each side."""

    name: str
    #: `None` when no source is configured, which reads differently from zero:
    #: one means "not connected", the other means "connected and empty".
    source: int | None = None
    target: int = 0
    #: False for anything the copy deliberately skips, so the UI can say why a
    #: row has a source count it is never going to receive.
    included: bool = True


class DatabaseStatus(ApiModel):
    environment: str
    #: Credential-free `host/database` labels. Never the URI: this is rendered
    #: in a browser and read out of an API response.
    target: str
    source: str | None = None
    source_configured: bool = False
    #: Whether a copy could run right now. When false, `blocked_reason` says
    #: what to fix, in a sentence meant for the person reading the screen.
    can_copy: bool = False
    blocked_reason: str | None = None
    #: The word the caller has to send back to confirm a destructive action.
    confirmation_phrase: str
    collections: list[CollectionCount] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)


class MaintenanceRequest(ApiModel):
    """The confirmation, which must match `DatabaseStatus.confirmation_phrase`.

    Typing the database name back is the same friction `scripts/_common.py`
    imposes on a production write, for the same reason: a yes/no prompt is
    answered by reflex, and naming the thing requires having read the line
    above it.
    """

    confirm: str


class CollectionResult(ApiModel):
    name: str
    removed: int = 0
    copied: int = 0


class MaintenanceResult(ApiModel):
    action: MaintenanceAction
    target: str
    source: str | None = None
    collections: list[CollectionResult] = Field(default_factory=list)
    documents_removed: int = 0
    documents_copied: int = 0
