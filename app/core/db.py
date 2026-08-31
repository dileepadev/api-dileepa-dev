"""MongoDB connection lifecycle.

The async PyMongo driver connects to the **same cluster and the same
collections** v1 used. Nothing here re-seeds or renames anything;
document shape changes are the migration scripts' job, not the app's.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
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
#
# `events` holds the v2 shape. The v1 rows that used to be here are copied to
# `events_v1_backup` by scripts/migrate_events_v1_to_v2.py before it rewrites
# them, so the original seven-field documents remain recoverable.
COLLECTIONS = {
    "about": "about",
    "experiences": "experiences",
    "educations": "educations",
    "tools": "tools",
    "communities": "communities",
    "videos": "videos",
    # New in v2.0.0, so both are named the way v2 would name them rather than
    # the way Mongoose would have.
    "pillars": "pillars",
    "speaking_topics": "speaking_topics",
    "blogs": "blogs",
    "events": "events",
    "projects": "projects",
    "uploads": "uploads",
    "users": "users",
    # Engagement. Neither holds anything a reader typed: `blog_views` holds one
    # opaque key per reader per post per window and expires itself, and
    # `blog_reactions` holds that same key against which reaction was chosen.
    # The counts a page reads are denormalised onto the post document, because
    # rendering a post should not aggregate a growing collection.
    "blog_views": "blog_views",
    "blog_reactions": "blog_reactions",
    "comments": "comments",
    "comment_reactions": "comment_reactions",
    "contacts": "contacts",
}

# Indexes the API depends on. Created on startup and safe to re-run.
#
# The names here are v2's. Mongoose named the ones it created after the field —
# `email_1`, `slug_1` — and Mongo rejects a second index over the same keys
# under a different name (`IndexOptionsConflict`). So these are reconciled by
# **key pattern, not by name**: an existing index over the same keys is reused
# whatever it is called. See `ensure_indexes`.
INDEXES: dict[str, list[tuple[list[tuple[str, int]], dict[str, Any]]]] = {
    "users": [([("email", ASCENDING)], {"unique": True, "name": "email_unique"})],
    "blogs": [
        ([("slug", ASCENDING)], {"unique": True, "name": "slug_unique"}),
        ([("publishedDate", ASCENDING)], {"name": "publishedDate"}),
        ([("tags", ASCENDING)], {"name": "tags"}),
    ],
    # The unique key is what makes a repeat view a no-op: the insert fails
    # rather than the handler deciding, so two concurrent requests cannot both
    # conclude they are the first. The TTL index is what stops this collection
    # growing without bound — Mongo deletes each row once its window passes.
    "blog_views": [
        ([("key", ASCENDING)], {"unique": True, "name": "key_unique"}),
        ([("expiresAt", ASCENDING)], {"expireAfterSeconds": 0, "name": "expiresAt_ttl"}),
    ],
    # One reaction per reader per post. The unique compound key is what lets a
    # second reaction from the same reader *replace* the first instead of
    # counting twice.
    "blog_reactions": [
        (
            [("slug", ASCENDING), ("key", ASCENDING)],
            {"unique": True, "name": "slug_key_unique"},
        ),
    ],
    # Reading a post's comments is the hot path — every post page does it — and
    # it always filters by slug and sorts by creation. `parentId` supports the
    # threading, and `key` is what groups a repeat commenter on the moderation
    # screen. Nothing here is unique: two people may say the same thing.
    "comments": [
        ([("slug", ASCENDING), ("createdAt", ASCENDING)], {"name": "slug_createdAt"}),
        ([("parentId", ASCENDING)], {"name": "parentId"}),
        ([("key", ASCENDING)], {"name": "key"}),
    ],
    # One reaction per reader per comment. The unique compound key is what lets
    # a second reaction replace the first rather than counting twice — the same
    # shape as `blog_reactions`, keyed on the comment instead of the slug.
    "comment_reactions": [
        (
            [("commentId", ASCENDING), ("key", ASCENDING)],
            {"unique": True, "name": "commentId_key_unique"},
        ),
    ],
    "projects": [
        ([("slug", ASCENDING)], {"unique": True, "name": "slug_unique"}),
        ([("status", ASCENDING)], {"name": "status"}),
        ([("tags", ASCENDING)], {"name": "tags"}),
    ],
    "events": [
        ([("slug", ASCENDING)], {"unique": True, "name": "slug_unique"}),
        ([("startAt", ASCENDING)], {"name": "startAt"}),
        ([("status", ASCENDING)], {"name": "status"}),
    ],
    "uploads": [([("publicId", ASCENDING)], {"unique": True, "name": "publicId_unique"})],
    "contacts": [([("createdAt", ASCENDING)], {"name": "createdAt"})],
}


# A comparable form of an index's key pattern. Mongo reports directions as ints
# but is documented to allow floats, and `list_indexes` preserves order, which
# matters: {a: 1, b: 1} and {b: 1, a: 1} are different indexes.
KeySignature = tuple[tuple[str, str], ...]


def _key_signature(keys: Iterable[tuple[str, Any]]) -> KeySignature:
    return tuple(
        (field, str(int(d)) if isinstance(d, (int, float)) else str(d)) for field, d in keys
    )


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

    async def _existing_indexes(
        self, collection: AsyncCollection[dict[str, Any]]
    ) -> dict[KeySignature, dict[str, Any]]:
        """What is already indexed on this collection, keyed by key pattern."""
        found: dict[KeySignature, dict[str, Any]] = {}
        async for index in await collection.list_indexes():
            found[_key_signature(index["key"].items())] = dict(index)
        return found

    async def ensure_indexes(self) -> None:
        """Reconcile the indexes the API relies on, without failing startup.

        Reconcile rather than create: this runs against a database Mongoose
        built, where `users.email` and `blogs.slug` are already indexed and
        already unique — just under Mongoose's names rather than ours. Asking
        for the same keys under a different name is an `IndexOptionsConflict`,
        not a no-op, so matching on the key pattern is what makes startup quiet
        against the existing cluster and correct against an empty one.

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

        created = reused = 0

        for name, specs in INDEXES.items():
            collection = self.collection(name)
            try:
                existing = await self._existing_indexes(collection)
            except PyMongoError:
                logger.warning("Could not list indexes on %s", name, exc_info=True)
                continue

            for keys, options in specs:
                index = existing.get(_key_signature(keys))

                if index is None:
                    try:
                        await collection.create_index(keys, **options)
                    except PyMongoError:
                        logger.warning(
                            "Could not create index %s on %s",
                            options.get("name"),
                            name,
                            exc_info=True,
                        )
                    else:
                        created += 1
                    continue

                reused += 1

                # The name differing is expected and harmless. Uniqueness not
                # being there is neither: the API relies on it to reject a
                # duplicate slug or a second account on one address, and Mongo
                # will not add the constraint to an index that already exists.
                if options.get("unique") and not index.get("unique"):
                    logger.warning(
                        "Index %r on %s covers %s but is not unique, and the API expects it "
                        "to be. Duplicates will not be rejected. Drop it and let this recreate "
                        "it, once you have confirmed there are no duplicates.",
                        index.get("name"),
                        name,
                        ", ".join(field for field, _ in keys),
                    )
                elif index.get("name") != options.get("name"):
                    logger.debug(
                        "Index over %s on %s already exists as %r; leaving it alone.",
                        ", ".join(field for field, _ in keys),
                        name,
                        index.get("name"),
                    )

        logger.info("Indexes reconciled: %d created, %d already present.", created, reused)


mongo = MongoConnection()
