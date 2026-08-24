"""In-memory `DocumentRepository`, used by the tests.

`AGENTS.md`: "Keep tests offline. No live API keys, no real MongoDB, no network
in a unit test." This is how that holds while the routers still exercise real
filtering, sorting and pagination.

The matcher supports exactly the operators the app uses. Anything else raises,
so a filter this fake cannot evaluate fails the test rather than silently
returning the wrong documents.
"""

from __future__ import annotations

import copy
from typing import Any

from bson import ObjectId

from app.core.errors import ConflictError
from app.repositories.base import Document, Filters, Sort, utc_now

_SUPPORTED_OPERATORS = {"$in", "$nin", "$ne", "$gt", "$gte", "$lt", "$lte", "$exists", "$regex"}


class _Missing:
    """Sentinel for an absent field, so `None` and "not present" stay distinct."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<missing>"


MISSING = _Missing()


def _resolve(document: Document, path: str) -> Any:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return MISSING
        current = current[part]
    return current


def _matches_condition(value: Any, condition: Any) -> bool:
    if isinstance(condition, dict) and any(k.startswith("$") for k in condition):
        unknown = {k for k in condition if k.startswith("$")} - _SUPPORTED_OPERATORS
        if unknown:
            raise NotImplementedError(f"InMemoryRepository cannot evaluate {sorted(unknown)}")
        for operator, operand in condition.items():
            if not _apply_operator(value, operator, operand):
                return False
        return True

    if value is MISSING:
        return condition is None
    # Mongo matches an array field when any element equals the operand.
    if isinstance(value, list) and not isinstance(condition, list):
        return condition in value
    return bool(value == condition)


def _apply_operator(value: Any, operator: str, operand: Any) -> bool:
    if operator == "$exists":
        return (value is not MISSING) == bool(operand)
    if value is MISSING:
        return operator in {"$ne", "$nin"}
    if operator == "$in":
        if isinstance(value, list):
            return any(item in operand for item in value)
        return value in operand
    if operator == "$nin":
        if isinstance(value, list):
            return all(item not in operand for item in value)
        return value not in operand
    if operator == "$ne":
        return bool(value != operand)
    if operator == "$regex":
        import re

        return bool(re.search(operand, str(value)))
    try:
        if operator == "$gt":
            return bool(value > operand)
        if operator == "$gte":
            return bool(value >= operand)
        if operator == "$lt":
            return bool(value < operand)
        if operator == "$lte":
            return bool(value <= operand)
    except TypeError:
        return False
    raise NotImplementedError(f"InMemoryRepository cannot evaluate {operator}")


def matches(document: Document, filters: Filters | None) -> bool:
    if not filters:
        return True
    for key, condition in filters.items():
        if key == "$or":
            if not any(matches(document, sub) for sub in condition):
                return False
            continue
        if key == "$and":
            if not all(matches(document, sub) for sub in condition):
                return False
            continue
        if key.startswith("$"):
            raise NotImplementedError(f"InMemoryRepository cannot evaluate {key}")
        if not _matches_condition(_resolve(document, key), condition):
            return False
    return True


class _SortKey:
    """Orders mixed and missing values the way Mongo does: absent sorts first."""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def __lt__(self, other: _SortKey) -> bool:
        left, right = self.value, other.value
        if left is MISSING or left is None:
            return not (right is MISSING or right is None)
        if right is MISSING or right is None:
            return False
        try:
            return bool(left < right)
        except TypeError:
            return str(left) < str(right)


class InMemoryRepository:
    """`DocumentRepository` backed by a list. Seeded documents are deep-copied."""

    def __init__(
        self,
        documents: list[Document] | None = None,
        *,
        label: str = "record",
        unique: tuple[str, ...] = (),
    ) -> None:
        self._label = label
        self._unique = unique
        self._documents: list[Document] = []
        for document in documents or []:
            seeded = copy.deepcopy(document)
            seeded.setdefault("_id", ObjectId())
            self._documents.append(seeded)

    @property
    def documents(self) -> list[Document]:
        return [copy.deepcopy(doc) for doc in self._documents]

    async def list(
        self,
        *,
        filters: Filters | None = None,
        sort: Sort | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        found = [doc for doc in self._documents if matches(doc, filters)]
        total = len(found)
        for field, direction in reversed(sort or []):
            found.sort(key=lambda doc, f=field: _SortKey(_resolve(doc, f)), reverse=direction < 0)  # type: ignore[misc]
        window = found[offset:] if offset else found
        if limit is not None:
            window = window[:limit]
        return [copy.deepcopy(doc) for doc in window], total

    async def find_one(self, filters: Filters) -> Document | None:
        for document in self._documents:
            if matches(document, filters):
                return copy.deepcopy(document)
        return None

    async def get(self, doc_id: str) -> Document | None:
        return await self.find_one({"_id": _as_object_id(doc_id)}) if doc_id else None

    async def create(self, data: Document) -> Document:
        now = utc_now()
        document = {**copy.deepcopy(data), "createdAt": now, "updatedAt": now}
        document.setdefault("_id", ObjectId())
        self._guard_unique(document, exclude=None)
        self._documents.append(document)
        return copy.deepcopy(document)

    async def update(self, doc_id: str, data: Document) -> Document | None:
        oid = _as_object_id(doc_id)
        if oid is None:
            return None
        return await self.update_one({"_id": oid}, data)

    async def update_one(
        self, filters: Filters, data: Document, *, upsert: bool = False
    ) -> Document | None:
        for document in self._documents:
            if matches(document, filters):
                changes = {k: v for k, v in copy.deepcopy(data).items() if k != "_id"}
                candidate = {**document, **changes}
                self._guard_unique(candidate, exclude=document["_id"])
                document.update(changes)
                document["updatedAt"] = utc_now()
                return copy.deepcopy(document)
        if not upsert:
            return None
        seed = {k: v for k, v in filters.items() if not k.startswith("$")}
        return await self.create({**seed, **data})

    async def delete(self, doc_id: str) -> Document | None:
        oid = _as_object_id(doc_id)
        if oid is None:
            return None
        return await self.delete_one({"_id": oid})

    async def delete_one(self, filters: Filters) -> Document | None:
        for index, document in enumerate(self._documents):
            if matches(document, filters):
                return self._documents.pop(index)
        return None

    async def upsert_by(self, field: str, value: Any, data: Document) -> Document:
        document = await self.update_one({field: value}, data, upsert=True)
        if document is None:  # pragma: no cover - upsert always returns a document
            raise ConflictError(f"Could not upsert {self._label} with {field} '{value}'.")
        return document

    async def set_order(self, order_by_id: dict[str, int]) -> int:
        updated = 0
        for doc_id, order in order_by_id.items():
            if await self.update(doc_id, {"order": order}) is not None:
                updated += 1
        return updated

    async def count(self, filters: Filters | None = None) -> int:
        return sum(1 for doc in self._documents if matches(doc, filters))

    def _guard_unique(self, candidate: Document, *, exclude: Any) -> None:
        for field in self._unique:
            value = _resolve(candidate, field)
            if value is MISSING:
                continue
            for document in self._documents:
                if document["_id"] == exclude:
                    continue
                if _resolve(document, field) == value:
                    raise ConflictError(
                        f"Another {self._label} already uses that {field}. Pick a different one.",
                        details={"field": field},
                    )


def _as_object_id(value: str) -> ObjectId | None:
    return ObjectId(value) if ObjectId.is_valid(value) else None
