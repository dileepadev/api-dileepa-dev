"""Index reconciliation against a database Mongoose already built.

`users.email` and `blogs.slug` are indexed and unique in the live cluster, named
`email_1` and `slug_1` because that is what Mongoose calls them. Asking Mongo for
the same keys under a different name is an `IndexOptionsConflict`, not a no-op,
so startup used to log two stack traces every time it ran against real data.

These run offline against a fake collection — `AGENTS.md` keeps the suite off
real MongoDB, and the logic worth pinning here is which calls get made, not
whether Mongo honours them.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from app.core.db import _key_signature, mongo


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    async def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        for document in self._documents:
            yield document


class FakeCollection:
    def __init__(self, indexes: list[dict[str, Any]]) -> None:
        self.indexes = indexes
        self.created: list[tuple[Any, dict[str, Any]]] = []

    async def list_indexes(self) -> FakeCursor:
        return FakeCursor(self.indexes)

    async def create_index(self, keys: Any, **options: Any) -> str:
        self.created.append((keys, options))
        return str(options.get("name", ""))


class FakeDatabase:
    name = "fake"

    def __init__(self, collections: dict[str, FakeCollection]) -> None:
        self._collections = collections

    def __getitem__(self, key: str) -> FakeCollection:
        return self._collections.setdefault(key, FakeCollection([]))

    async def command(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"ok": 1}


def index(name: str, field: str, *, unique: bool = False) -> dict[str, Any]:
    document: dict[str, Any] = {"v": 2, "key": {field: 1}, "name": name}
    if unique:
        document["unique"] = True
    return document


@pytest.fixture
def collections(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, FakeCollection]]:
    store: dict[str, FakeCollection] = {}
    monkeypatch.setattr(mongo, "_database", FakeDatabase(store))
    yield store
    monkeypatch.setattr(mongo, "_database", None)


class TestKeySignature:
    def test_int_and_float_directions_compare_equal(self) -> None:
        # Mongo reports 1, but the spec allows a float and drivers have returned
        # one. A mismatch here would mean recreating an index that exists.
        assert _key_signature([("email", 1)]) == _key_signature([("email", 1.0)])

    def test_field_order_is_significant(self) -> None:
        # {a: 1, b: 1} and {b: 1, a: 1} are genuinely different indexes.
        assert _key_signature([("a", 1), ("b", 1)]) != _key_signature([("b", 1), ("a", 1)])

    def test_direction_is_significant(self) -> None:
        assert _key_signature([("a", 1)]) != _key_signature([("a", -1)])

    def test_non_numeric_directions_survive(self) -> None:
        assert _key_signature([("a", "text")]) == (("a", "text"),)


class TestReconciliation:
    async def test_mongoose_named_index_is_reused_not_recreated(
        self, collections: dict[str, FakeCollection]
    ) -> None:
        # The bug: this used to attempt email_unique over the same keys and get
        # back IndexOptionsConflict, with a stack trace, on every startup.
        collections["users"] = FakeCollection([index("email_1", "email", unique=True)])
        collections["blogs"] = FakeCollection([index("slug_1", "slug", unique=True)])

        await mongo.ensure_indexes()

        assert collections["users"].created == []
        blog_indexes = [options.get("name") for _, options in collections["blogs"].created]
        assert "slug_unique" not in blog_indexes
        # The two blogs indexes Mongoose never made are still created.
        assert set(blog_indexes) == {"publishedDate", "tags"}

    async def test_missing_indexes_are_created(
        self, collections: dict[str, FakeCollection]
    ) -> None:
        await mongo.ensure_indexes()
        assert [options["name"] for _, options in collections["users"].created] == ["email_unique"]

    async def test_an_exact_match_is_left_alone(
        self, collections: dict[str, FakeCollection]
    ) -> None:
        collections["users"] = FakeCollection([index("email_unique", "email", unique=True)])
        await mongo.ensure_indexes()
        assert collections["users"].created == []

    async def test_a_non_unique_index_where_uniqueness_is_needed_warns(
        self, collections: dict[str, FakeCollection], caplog: pytest.LogCaptureFixture
    ) -> None:
        # Reusing by key pattern must not quietly accept a weaker index: Mongo
        # will not add the constraint to one that already exists, so silence
        # here would mean duplicate slugs sailing through.
        collections["blogs"] = FakeCollection([index("slug_1", "slug")])

        with caplog.at_level(logging.WARNING, logger="app.core.db"):
            await mongo.ensure_indexes()

        assert any("is not unique" in record.getMessage() for record in caplog.records), (
            "expected a warning that the existing index lacks the uniqueness constraint"
        )

    async def test_a_differently_named_index_does_not_warn(
        self, collections: dict[str, FakeCollection], caplog: pytest.LogCaptureFixture
    ) -> None:
        # The whole point: a name mismatch is normal during the migration and
        # must not produce noise on every single startup.
        collections["users"] = FakeCollection([index("email_1", "email", unique=True)])

        with caplog.at_level(logging.WARNING, logger="app.core.db"):
            await mongo.ensure_indexes()

        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    async def test_an_unreachable_database_skips_the_whole_thing(
        self, monkeypatch: pytest.MonkeyPatch, collections: dict[str, FakeCollection]
    ) -> None:
        async def down() -> bool:
            return False

        monkeypatch.setattr(mongo, "ping", down)
        await mongo.ensure_indexes()
        assert collections == {}
