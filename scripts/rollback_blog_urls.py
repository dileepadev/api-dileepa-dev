"""Put the blog rows back the way `migrate_blog_urls.py` found them.

The reason `legacy` is kept for a release. Reverses the rewrite for any row that
still carries one.

    uv run python -m scripts.rollback_blog_urls
    uv run python -m scripts.rollback_blog_urls --apply
"""

from __future__ import annotations

import argparse
from typing import Any

from scripts._common import banner, base_parser, database, run, summarise


async def main(args: argparse.Namespace) -> int:
    banner("Roll back blog URLs")
    counts = {"rows with legacy": 0, "rows restored": 0, "nothing to restore": 0}

    async with database(args) as db:
        async for row in db["blogs"].find({"legacy": {"$exists": True}}):
            counts["rows with legacy"] += 1
            legacy = row.get("legacy") or {}
            restore: dict[str, Any] = {
                key: legacy[key]
                for key in ("link", "bannerUrl", "date", "excerpt")
                if legacy.get(key) is not None
            }
            if not restore:
                counts["nothing to restore"] += 1
                continue

            print(f"  {row.get('slug')} -> link {restore.get('link')!r}")
            counts["rows restored"] += 1
            if args.apply:
                await db["blogs"].update_one(
                    {"_id": row["_id"]},
                    {
                        "$set": restore,
                        "$unset": {"legacy": "", "path": "", "canonicalUrl": ""},
                    },
                )

    summarise(counts, apply=args.apply)
    return 0


if __name__ == "__main__":
    run(main, base_parser(__doc__ or "").parse_args())
