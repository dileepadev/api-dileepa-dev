"""Shared plumbing for the migration and operations scripts.

Every script that writes takes `--apply`. Without it nothing is written and the
script prints what it would have done. That is the default on purpose: these run
against the live cluster.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the changes. Without this the script only reports what it would do.",
    )
    parser.add_argument(
        "--uri",
        default=None,
        help="MongoDB URI. Defaults to MONGODB_URI from the environment.",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Database name. Defaults to MONGODB_DB, or the URI's default database.",
    )
    return parser


@asynccontextmanager
async def database(args: argparse.Namespace) -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    settings = get_settings()
    uri = args.uri or settings.mongodb_uri
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(uri, tz_aware=True)
    try:
        name = args.database or settings.mongodb_db
        db = client[name] if name else client.get_default_database()
        yield db
    finally:
        await client.close()


def banner(title: str, *, apply: bool) -> None:
    mode = "APPLY — writing changes" if apply else "DRY RUN — nothing will be written"
    print(f"\n{title}\n{'=' * len(title)}\n{mode}\n")


def summarise(counts: dict[str, int], *, apply: bool) -> None:
    print("\nSummary")
    for key, value in counts.items():
        print(f"  {key:32} {value}")
    if not apply:
        print("\nNothing was written. Re-run with --apply once the output above looks right.")


def run(
    main: Callable[[argparse.Namespace], Coroutine[Any, Any, int]],
    args: argparse.Namespace,
) -> None:
    sys.exit(asyncio.run(main(args)))
