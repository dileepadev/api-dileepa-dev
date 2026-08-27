"""Development-only database maintenance.

Two operations, both destructive to the **development** database and neither
capable of touching production:

- `POST /maintenance/database/copy` — replace this database's contents with a
  copy of the configured source, so a developer can work against real content.
- `POST /maintenance/database/clear` — empty this database.

**Why the direction cannot invert.** A copy has a source and a target, and the
only interesting bug is the one that swaps them. So the target is never chosen:
it is `mongo`, the connection this process already opened from `MONGODB_URI`,
and it is the only connection anything here writes through. The source is opened
per request, read from, and closed. There is no code path that writes to the
source, so there is no configuration that makes this run backwards.

**Five guards, in order of how much they would have to fail together.**

1. `app/main.py` does not register this router when `ENVIRONMENT=production`.
   The routes do not exist on the production API — not "exist and refuse".
2. Every handler re-checks anyway, so re-registering the router by accident
   still yields a 403 rather than a wipe.
3. `SOURCE_MONGODB_URI` must be set. Unset disables the feature.
4. Source and target must be different databases, compared on their
   credential-free `host/database` labels so two spellings of one cluster
   cannot pass as two.
5. The caller must send the target database's own name back as `confirm`.

And a sixth that is not code: the credential in `SOURCE_MONGODB_URI` should
belong to an Atlas user with `read` on production and nothing else. Then the
worst outcome of all five guards failing at once is a failed write.

`users` is never copied. It holds the password hash the admin signs in with,
and overwriting the development account with production's would change the
credentials of the environment you are standing in, mid-session.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.core.db import COLLECTIONS, mongo
from app.core.deps import AdminUser, SettingsDep
from app.core.errors import BadRequestError, ForbiddenError, ServiceUnavailableError
from app.models.maintenance import (
    CollectionCount,
    CollectionResult,
    DatabaseStatus,
    MaintenanceRequest,
    MaintenanceResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

#: Never copied. See the module docstring.
EXCLUDED_COLLECTIONS = frozenset({"users"})

#: The collections the copy covers, in the order they are reported.
COPIED_COLLECTIONS = [name for name in COLLECTIONS if name not in EXCLUDED_COLLECTIONS]

#: Documents per `insert_many`. The database is small enough that this never
#: matters today; it is here so that it still does not matter later.
BATCH = 500


def _confirmation_phrase(settings: Settings) -> str:
    """What the caller must send back: the target database's own name."""
    return settings.database_label.rsplit("/", 1)[-1]


def _require_non_production(settings: Settings) -> None:
    """Guard 2. Guard 1 is that this router is not registered in production."""
    if settings.is_production:
        raise ForbiddenError(
            "These routes do not run against production. They empty the database they are "
            "pointed at, and this process is pointed at production.",
            code="maintenance_forbidden_in_production",
        )


def _require_usable_source(settings: Settings) -> None:
    """Guards 3 and 4."""
    if not settings.copy_source_configured:
        raise ServiceUnavailableError(
            "No source database is configured. Set SOURCE_MONGODB_URI in .env.development to "
            "an Atlas user with read access to production, then restart the API.",
            code="copy_source_not_configured",
        )
    if settings.source_is_target:
        raise BadRequestError(
            f"The source and the target are both {settings.database_label}. A copy onto itself "
            "would empty the collection it is reading from.",
            code="copy_source_is_target",
        )


def _require_confirmation(settings: Settings, payload: MaintenanceRequest) -> None:
    """Guard 5."""
    expected = _confirmation_phrase(settings)
    if payload.confirm.strip() != expected:
        raise BadRequestError(
            f"Send the target database's name as 'confirm' to continue. Expected {expected!r}.",
            code="confirmation_mismatch",
        )


@asynccontextmanager
async def _source_database(settings: Settings) -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    """Open the source, read-only by intent and by convention.

    Opened per request rather than held for the life of the process: this is
    used a handful of times a week at most, and a connection that only exists
    while it is being read from is one that cannot be reached by anything else.
    """
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        settings.source_mongodb_uri,
        tz_aware=True,
        serverSelectionTimeoutMS=10_000,
    )
    try:
        database = (
            client[settings.source_mongodb_db]
            if settings.source_mongodb_db
            else client.get_default_database()
        )
        yield database
    finally:
        await client.close()


@router.get(
    "/database",
    response_model=DatabaseStatus,
    summary="Where this API is pointed, and what a copy would move",
)
async def database_status(settings: SettingsDep, _: AdminUser) -> DatabaseStatus:
    """Both databases, their document counts, and whether a copy can run.

    Reported before anything is offered, because the one question worth
    answering before a destructive action is "which database am I about to
    empty" — and the answer should not be inferred from which tab is open.
    """
    _require_non_production(settings)

    blocked: str | None = None
    if not settings.copy_source_configured:
        blocked = (
            "No source database is configured. Set SOURCE_MONGODB_URI in .env.development "
            "to an Atlas user with read access to production, then restart the API."
        )
    elif settings.source_is_target:
        blocked = (
            f"The source and the target are both {settings.database_label}. "
            "A copy onto itself would empty the collection it is reading from."
        )

    names = list(COLLECTIONS)
    source_counts: dict[str, int] = {}

    if blocked is None:
        try:
            async with _source_database(settings) as source:
                # Gathered, not looped. Counting fifteen collections on each
                # side is thirty round trips to Atlas, and sequentially that is
                # around twelve seconds of a screen showing nothing — long
                # enough to read as broken. Concurrently it is one round trip's
                # worth of latency.
                source_counts = dict(
                    zip(
                        names,
                        await asyncio.gather(
                            *(source[COLLECTIONS[name]].count_documents({}) for name in names)
                        ),
                        strict=True,
                    )
                )
        except PyMongoError:
            logger.warning("Could not read the copy source", exc_info=True)
            blocked = (
                "The source database could not be reached. Check SOURCE_MONGODB_URI and that "
                "this machine's address is allowed in the Atlas network access list."
            )

    target_counts = dict(
        zip(
            names,
            await asyncio.gather(*(mongo.collection(name).count_documents({}) for name in names)),
            strict=True,
        )
    )

    counts = [
        CollectionCount(
            name=name,
            source=source_counts.get(name) if blocked is None else None,
            target=target_counts[name],
            included=name not in EXCLUDED_COLLECTIONS,
        )
        for name in names
    ]

    return DatabaseStatus(
        environment=settings.environment,
        target=settings.database_label,
        source=settings.source_database_label,
        source_configured=settings.copy_source_configured,
        can_copy=blocked is None,
        blocked_reason=blocked,
        confirmation_phrase=_confirmation_phrase(settings),
        collections=counts,
        excluded=sorted(EXCLUDED_COLLECTIONS),
    )


@router.post(
    "/database/clear",
    response_model=MaintenanceResult,
    summary="Empty this database",
)
async def clear_database(
    payload: MaintenanceRequest, settings: SettingsDep, _: AdminUser
) -> MaintenanceResult:
    """Remove every document from the collections this API owns.

    `delete_many` rather than `drop`: the collection and its indexes survive, so
    the next write is validated the same way it would have been before. Dropping
    and letting `ensure_indexes` rebuild on the next restart would leave a
    window where a duplicate slug inserts cleanly.
    """
    _require_non_production(settings)
    _require_confirmation(settings, payload)

    results: list[CollectionResult] = []
    removed_total = 0

    for name in COPIED_COLLECTIONS:
        removed = (await mongo.collection(name).delete_many({})).deleted_count
        removed_total += removed
        results.append(CollectionResult(name=name, removed=removed))

    logger.warning(
        "Cleared %s: %d documents removed across %d collections.",
        settings.database_label,
        removed_total,
        len(results),
    )
    return MaintenanceResult(
        action="clear",
        target=settings.database_label,
        source=None,
        collections=results,
        documents_removed=removed_total,
    )


@router.post(
    "/database/copy",
    response_model=MaintenanceResult,
    summary="Replace this database's contents with the source's",
)
async def copy_database(
    payload: MaintenanceRequest, settings: SettingsDep, _: AdminUser
) -> MaintenanceResult:
    """Copy the source into this database, one collection at a time.

    `_id`s are preserved, so a document keeps the identity it has in the
    source and every reference to it survives the copy — which is what makes
    the result testable against the same URLs.

    Not a transaction. Each collection is emptied and refilled in turn, so an
    interruption leaves the earlier collections copied and the later ones
    untouched. That is acceptable here in a way it would not be in production:
    the fix is to run it again, and the whole point of the target is that
    nothing depends on its contents.
    """
    _require_non_production(settings)
    _require_usable_source(settings)
    _require_confirmation(settings, payload)

    results: list[CollectionResult] = []
    removed_total = copied_total = 0

    async with _source_database(settings) as source:
        for name in COPIED_COLLECTIONS:
            physical = COLLECTIONS[name]
            target = mongo.collection(name)

            documents = [document async for document in source[physical].find({})]

            # Emptied only once the source has been read: a source that fails
            # mid-read leaves the target as it was rather than empty.
            removed = (await target.delete_many({})).deleted_count

            copied = 0
            for start in range(0, len(documents), BATCH):
                batch = documents[start : start + BATCH]
                await target.insert_many(batch, ordered=False)
                copied += len(batch)

            removed_total += removed
            copied_total += copied
            results.append(CollectionResult(name=name, removed=removed, copied=copied))

    logger.warning(
        "Copied %s into %s: %d documents in, %d replaced.",
        settings.source_database_label,
        settings.database_label,
        copied_total,
        removed_total,
    )
    return MaintenanceResult(
        action="copy",
        target=settings.database_label,
        source=settings.source_database_label,
        collections=results,
        documents_removed=removed_total,
        documents_copied=copied_total,
    )
