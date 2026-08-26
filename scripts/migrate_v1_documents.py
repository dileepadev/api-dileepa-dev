"""Backfill v1 documents into the v2.0.0 shape.

Every collection ported from v1 is missing the fields the contract says every
resource carries: `published`, `order`, `meta`, `createdAt`, `updatedAt`. v1
also stored ordering as `index`.

**This runs before traffic moves.** The API reads `index` as `order` and treats
a missing `published` as published, so it is correct against an untouched
database — but sorting happens in MongoDB, before that aliasing, so a
half-migrated collection sorts v2 documents above v1 ones. Run this to
completion, then cut over.

    uv run python -m scripts.migrate_v1_documents            # dry run
    uv run python -m scripts.migrate_v1_documents --apply

Safe to re-run: every document is matched on the fields it is missing.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Any

from scripts._common import banner, base_parser, database, run, summarise

COLLECTIONS = (
    "about",
    "experiences",
    "educations",
    "tools",
    "communities",
    "videos",
    "blogs",
)


async def main(args: argparse.Namespace) -> int:
    banner("Backfill v1 documents")
    counts: dict[str, int] = {}
    now = datetime.now(UTC)

    async with database(args) as db:
        for name in COLLECTIONS:
            collection = db[name]
            renamed = 0
            filled = 0

            async for document in collection.find({}):
                updates: dict[str, Any] = {}
                unsets: dict[str, str] = {}

                # `index` and `order` mean the same thing: priority, higher
                # first. Rename rather than duplicate, so nothing has both.
                if "index" in document and "order" not in document:
                    updates["order"] = document["index"]
                    unsets["index"] = ""
                    renamed += 1
                elif "order" not in document:
                    updates["order"] = 0

                # Absent means published: everything in the database today is
                # live on the site.
                if "published" not in document:
                    updates["published"] = True
                if "meta" not in document:
                    updates["meta"] = {}
                if "createdAt" not in document:
                    # The ObjectId carries its own creation time, which is a
                    # better guess than "now" for a document written years ago.
                    updates["createdAt"] = getattr(document["_id"], "generation_time", now)
                if "updatedAt" not in document:
                    updates["updatedAt"] = updates.get("createdAt", now)

                if not updates and not unsets:
                    continue
                filled += 1
                if args.apply:
                    operation: dict[str, Any] = {"$set": updates}
                    if unsets:
                        operation["$unset"] = unsets
                    await collection.update_one({"_id": document["_id"]}, operation)

            counts[f"{name}: documents updated"] = filled
            counts[f"{name}: index renamed to order"] = renamed

    summarise(counts, apply=args.apply)
    return 0


if __name__ == "__main__":
    run(main, base_parser(__doc__ or "").parse_args())
