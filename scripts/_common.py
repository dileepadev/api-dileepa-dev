"""Shared plumbing for the migration and operations scripts.

Every script that writes takes `--apply`. Without it nothing is written and the
script prints what it would have done. That is the default on purpose: these run
against the live cluster.

`--apply` alone is not enough for production. `database()` prints the
environment and the database it is about to open, and when that environment is
production it makes the operator type the database name back before anything
happens. The scripts here rewrite blog URLs and reshape event documents —
running one against the wrong cluster is not something a dry run can undo after
the fact.
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

from app.core.config import database_label, get_settings


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
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the production confirmation prompt. For scripted runs only.",
    )
    return parser


class TargetRefusedError(RuntimeError):
    """The operator declined the target, or could not be asked."""


def _confirm_production(label: str, *, assume_yes: bool) -> None:
    """Make the operator name the production database before it is written to.

    Typing the name back is deliberate friction. A y/n prompt is answered by
    reflex; retyping `dileepa` requires having read the line above it.
    """
    if assume_yes:
        print("  --yes was given, so the production prompt is skipped.\n")
        return

    if not sys.stdin.isatty():
        raise TargetRefusedError(
            "This is a production database and stdin is not a terminal, so the "
            "confirmation cannot be asked for. Re-run interactively, or pass --yes "
            "if this really is a scripted run."
        )

    expected = label.rsplit("/", 1)[-1]
    print("  This writes to PRODUCTION.")
    answer = input(f"  Type the database name ({expected}) to continue: ").strip()
    print()
    if answer != expected:
        raise TargetRefusedError("That did not match the database name. Nothing was written.")


@asynccontextmanager
async def database(args: argparse.Namespace) -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    settings = get_settings()
    uri = args.uri or settings.mongodb_uri
    name = args.database or settings.mongodb_db
    label = database_label(uri, name)
    apply = bool(getattr(args, "apply", False))

    print(f"  ENVIRONMENT  {settings.environment}")
    print(f"  DATABASE     {label}")
    print(f"  MODE         {'APPLY — writing changes' if apply else 'DRY RUN — no writes'}")
    print()

    # A dry run reads and reports, so it needs no confirmation wherever it runs.
    if apply and settings.is_production:
        _confirm_production(label, assume_yes=bool(getattr(args, "yes", False)))

    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(uri, tz_aware=True)
    try:
        db = client[name] if name else client.get_default_database()
        yield db
    finally:
        await client.close()


def banner(title: str) -> None:
    """The script's title. `database()` prints the target and the mode."""
    print(f"\n{title}\n{'=' * len(title)}")


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
    try:
        sys.exit(asyncio.run(main(args)))
    except TargetRefusedError as exc:
        print(f"\nStopped: {exc}")
        sys.exit(1)
