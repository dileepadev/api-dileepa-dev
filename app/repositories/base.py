"""Document storage behind one narrow interface.

Routers never touch a driver. They take a `DocumentRepository`, which has two
implementations: `MongoRepository` for the real database and `InMemoryRepository`
for tests. That is what lets the contract tests run with no network and no live
MongoDB, which `AGENTS.md` requires.

Filters are Mongo-shaped dicts restricted to the operators this API actually
uses — `$in`, `$ne`, `$gte`, `$lte`, `$lt`, `$gt`, `$exists`, `$or`. The
in-memory matcher implements exactly that set and nothing more, so a filter the
fake cannot evaluate raises instead of quietly returning the wrong rows.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.errors import ConflictError

if TYPE_CHECKING:
    from pymongo.asynchronous.collection import AsyncCollection

Document = dict[str, Any]
Filters = dict[str, Any]
Sort = list[tuple[str, int]]


def utc_now() -> datetime:
    return datetime.now(UTC)


def is_object_id(value: str) -> bool:
    return ObjectId.is_valid(value)


class DocumentRepository(Protocol):
    """The storage surface the routers are allowed to use."""

    async def list(
        self,
        *,
        filters: Filters | None = None,
        sort: Sort | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[Document], int]: ...

    async def find_one(self, filters: Filters) -> Document | None: ...

    async def get(self, doc_id: str) -> Document | None: ...

    async def create(self, data: Document) -> Document: ...

    async def update(self, doc_id: str, data: Document) -> Document | None: ...

    async def update_one(
        self, filters: Filters, data: Document, *, upsert: bool = False
    ) -> Document | None: ...

    async def delete(self, doc_id: str) -> Document | None: ...

    async def delete_one(self, filters: Filters) -> Document | None: ...

    async def upsert_by(self, field: str, value: Any, data: Document) -> Document: ...

    async def set_order(self, order_by_id: dict[str, int]) -> int: ...

    async def count(self, filters: Filters | None = None) -> int: ...


class MongoRepository:
    """`DocumentRepository` over a real collection."""

    def __init__(self, collection: AsyncCollection[Document], *, label: str) -> None:
        self._collection = collection
        self._label = label

    async def list(
        self,
        *,
        filters: Filters | None = None,
        sort: Sort | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        query = filters or {}
        total = await self._collection.count_documents(query)
        cursor = self._collection.find(query)
        if sort:
            cursor = cursor.sort(sort)
        if offset:
            cursor = cursor.skip(offset)
        if limit is not None:
            cursor = cursor.limit(limit)
        return [doc async for doc in cursor], total

    async def find_one(self, filters: Filters) -> Document | None:
        return await self._collection.find_one(filters)

    async def get(self, doc_id: str) -> Document | None:
        try:
            oid = ObjectId(doc_id)
        except (InvalidId, TypeError):
            # A malformed id is a miss, not a 500. The router turns it into a 404.
            return None
        return await self._collection.find_one({"_id": oid})

    async def create(self, data: Document) -> Document:
        now = utc_now()
        document = {**data, "createdAt": now, "updatedAt": now}
        try:
            result = await self._collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise self._conflict(exc) from exc
        return {**document, "_id": result.inserted_id}

    async def update(self, doc_id: str, data: Document) -> Document | None:
        try:
            oid = ObjectId(doc_id)
        except (InvalidId, TypeError):
            return None
        return await self._update_by_filter({"_id": oid}, data, upsert=False)

    async def update_one(
        self, filters: Filters, data: Document, *, upsert: bool = False
    ) -> Document | None:
        return await self._update_by_filter(filters, data, upsert=upsert)

    async def _update_by_filter(
        self, filters: Filters, data: Document, *, upsert: bool
    ) -> Document | None:
        changes = {k: v for k, v in data.items() if k != "_id"}
        update: dict[str, Any] = {"$set": {**changes, "updatedAt": utc_now()}}
        if upsert:
            update["$setOnInsert"] = {"createdAt": utc_now()}
        try:
            return await self._collection.find_one_and_update(
                filters,
                update,
                upsert=upsert,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as exc:
            raise self._conflict(exc) from exc

    async def delete(self, doc_id: str) -> Document | None:
        try:
            oid = ObjectId(doc_id)
        except (InvalidId, TypeError):
            return None
        return await self._collection.find_one_and_delete({"_id": oid})

    async def delete_one(self, filters: Filters) -> Document | None:
        return await self._collection.find_one_and_delete(filters)

    async def upsert_by(self, field: str, value: Any, data: Document) -> Document:
        document = await self._update_by_filter({field: value}, data, upsert=True)
        if document is None:  # pragma: no cover - upsert always returns a document
            raise ConflictError(f"Could not upsert {self._label} with {field} '{value}'.")
        return document

    async def set_order(self, order_by_id: dict[str, int]) -> int:
        updated = 0
        for doc_id, order in order_by_id.items():
            result = await self.update(doc_id, {"order": order})
            if result is not None:
                updated += 1
        return updated

    async def count(self, filters: Filters | None = None) -> int:
        return await self._collection.count_documents(filters or {})

    def _conflict(self, exc: DuplicateKeyError) -> ConflictError:
        field = _duplicate_field(exc)
        if field:
            return ConflictError(
                f"Another {self._label} already uses that {field}. Pick a different one.",
                details={"field": field},
            )
        return ConflictError(f"That {self._label} conflicts with one that already exists.")


_INDEX_FIELD = re.compile(r"index: (?P<name>[A-Za-z0-9_.]+?)_(-?1|unique)")


def _duplicate_field(exc: DuplicateKeyError) -> str | None:
    key_pattern = (exc.details or {}).get("keyPattern") if exc.details else None
    if isinstance(key_pattern, dict) and key_pattern:
        return str(next(iter(key_pattern)))
    match = _INDEX_FIELD.search(str(exc))
    return match.group("name") if match else None
