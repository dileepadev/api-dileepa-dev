"""Recompute `blogs.commentCount` from the comments themselves.

The counter on a post is denormalised: it exists so the blog index can show
"12 comments" without reading every thread, which is the whole reason not to
compute it on read. `app/routers/comments.py` keeps it correct with `$inc` on
the four paths that can change it -- a public post, an owner reply, a
publish/unpublish, and a delete.

Denormalised counters drift. A write that lands while the process is being
replaced, a row edited directly in the database, or a bug in a future path all
leave the stored number disagreeing with reality. This script is the repair:
it counts published comments per slug and writes the truth back.

It is also the backfill. A post that predates the field has no `commentCount`
at all; `$inc` treats that as zero and counts correctly from the next comment
onward, but the field stays absent until something writes it, and an absent
field is indistinguishable from a genuine zero when reading raw documents.

Safe to run at any time, on any environment, as often as you like -- it only
ever writes a number it has just derived.

    uv run python -m scripts.reconcile_comment_counts
    uv run python -m scripts.reconcile_comment_counts --apply
"""

from __future__ import annotations

import argparse
from typing import Any

from scripts._common import base_parser, database, run, summarise


async def main(args: argparse.Namespace) -> int:
    counts = {"posts seen": 0, "already correct": 0, "corrected": 0, "backfilled": 0}

    async with database(args) as db:
        # One grouped read rather than a query per post: the drift check should
        # not itself be the expensive thing the counter exists to avoid.
        pipeline: list[dict[str, Any]] = [
            {"$match": {"published": {"$ne": False}}},
            {"$group": {"_id": "$slug", "n": {"$sum": 1}}},
        ]
        cursor = await db["comments"].aggregate(pipeline)
        actual: dict[str, int] = {str(row["_id"]): int(row["n"]) async for row in cursor}

        async for post in db["blogs"].find({}, {"slug": 1, "commentCount": 1}).sort("slug", 1):
            counts["posts seen"] += 1
            slug = str(post.get("slug", ""))
            stored = post.get("commentCount")
            truth = actual.get(slug, 0)

            if stored == truth:
                counts["already correct"] += 1
                continue

            if stored is None:
                counts["backfilled"] += 1
                print(f"  {slug}: absent -> {truth}")
            else:
                counts["corrected"] += 1
                print(f"  {slug}: {stored} -> {truth}  (drifted by {truth - int(stored)})")

            if args.apply:
                await db["blogs"].update_one(
                    {"_id": post["_id"]}, {"$set": {"commentCount": truth}}
                )

    summarise(counts, apply=args.apply)
    return 0


if __name__ == "__main__":
    run(main, base_parser(__doc__ or "").parse_args())
