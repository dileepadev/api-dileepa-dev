"""Aliases for the fixture types, so signatures stay readable."""

from __future__ import annotations

from app.repositories.memory import InMemoryRepository

Repos = dict[str, InMemoryRepository]
Headers = dict[str, str]


async def must_find(repo: InMemoryRepository, filters: dict[str, object]) -> dict[str, object]:
    """`find_one`, asserting the document exists.

    Test bodies read better without a `None` check on every seeded lookup, and a
    missing seed should fail loudly at the lookup rather than three lines later.
    """
    document = await repo.find_one(filters)
    assert document is not None, f"No seeded document matching {filters}"
    return document
