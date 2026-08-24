"""MongoDB connection lifecycle.

The async PyMongo driver connects to the **same cluster and the same
collections** the NestJS app uses. Nothing here re-seeds or renames anything;
document shape changes are the migration scripts' job, not the app's.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pymongo import ASCENDING, AsyncMongoClient
from pymongo.errors import PyMongoError

from app.core.config import Settings

if TYPE_CHECKING:
    from pymongo.asynchronous.collection import AsyncCollection
    from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)

# Collection names as they exist in Atlas today. Mongoose pluralised the model
# name for anything without an explicit `collection:` option, which is why
# `blogs`, `events`, `videos` and `uploads` look inconsistent with the rest.
COLLECTIONS = {
    "about": "about",
    "experiences": "experiences",
    "educations": "educations",
    "tools": "tools",
    "communities": "communities",
    "videos": "videos",
    "blogs": "blogs",
    "events": "events",
    "sessions": "sessions",
    "projects": "projects",
    "uploads": "uploads",
    "users": "users",
}

# Indexes the API depends on. Created on startup and safe to re-run: Mongo
# treats an identical `create_index` as a no-op.
INDEXES: dict[str, list[tuple[list[tuple[str, int]], dict[str, Any]]]] = {
    "users": [([("email", ASCENDING)], {"unique": True, "name": "email_unique"})],
    "blogs": [
        ([("slug", ASCENDING)], {"unique": True, "name": "slug_unique"}),
        ([("publishedDate", ASCENDING)], {"name": "publishedDate"}),
        ([("tags", ASCENDING)], {"name": "tags"}),
    ],
    "projects": [
        ([("slug", ASCENDING)], {"unique": True, "name": "slug_unique"}),
        ([("status", ASCENDING)], {"name": "status"}),
        ([("tags", ASCENDING)], {"name": "tags"}),
    ],
    "sessions": [
        ([("slug", ASCENDING)], {"unique": True, "name": "slug_unique"}),
        ([("startAt", ASCENDING)], {"name": "startAt"}),
        ([("status", ASCENDING)], {"name": "status"}),
    ],
    "uploads": [([("publicId", ASCENDING)], {"unique": True, "name": "publicId_unique"})],
}


class MongoConnection:
    """Holds the client for the process. Opened and closed by the app lifespan."""

    def __init__(self) -> None:
        self._client: AsyncMongoClient[dict[str, Any]] | None = None
        self._database: AsyncDatabase[dict[str, Any]] | None = None

    async def connect(self, settings: Settings) -> None:
        self._client = AsyncMongoClient(
            settings.mongodb_uri,
            tz_aware=True,
            serverSelectionTimeoutMS=10_000,
        )
        self._database = (
            self._client[settings.mongodb_db]
            if settings.mongodb_db
            else self._client.get_default_database()
        )
        logger.info("Connected to MongoDB database %s", self._database.name)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._database = None

    @property
    def database(self) -> AsyncDatabase[dict[str, Any]]:
        if self._database is None:
            raise RuntimeError("MongoDB is not connected. This is a startup ordering bug.")
        return self._database

    def collection(self, name: str) -> AsyncCollection[dict[str, Any]]:
        return self.database[COLLECTIONS.get(name, name)]

    async def ping(self) -> bool:
        try:
            await self.database.command("ping")
        except PyMongoError:
            logger.warning("MongoDB ping failed", exc_info=True)
            return False
        return True

    async def ensure_indexes(self) -> None:
        """Create the indexes the API relies on, without failing startup.

        A user without `createIndex` rights should not take the API down; the
        queries still work, they are just slower, and the warning says so.

        The ping gate matters more than it looks. Without it, an unreachable
        cluster costs one full server-selection timeout *per index* — around two
        minutes of startup, long enough for a platform health check to give up
        on the deployment. One ping fails in one timeout, and the API comes up
        and reports itself degraded through `/health`.
        """
        if not await self.ping():
            logger.warning(
                "Skipping index creation: MongoDB is unreachable. "
                "The API is starting anyway and /health will report it as down."
            )
            return

        for name, specs in INDEXES.items():
            collection = self.collection(name)
            for keys, options in specs:
                try:
                    await collection.create_index(keys, **options)
                except PyMongoError:
                    logger.warning(
                        "Could not create index %s on %s", options.get("name"), name, exc_info=True
                    )


mongo = MongoConnection()
