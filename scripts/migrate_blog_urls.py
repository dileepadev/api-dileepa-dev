"""Rewrite the blog rows off `blog.dileepa.dev`.

**This is the destructive one.** All 18 rows carry absolute URLs on a host that
stops serving. Before running it with `--apply`:

1. Take a MongoDB backup and **restore-test it**. Not just take it.
2. Run this without `--apply` and read the diff it prints.
3. Only then apply.

The old values are kept under `legacy: { link, bannerUrl, date, excerpt }` for
one release, so the change is reversible. `scripts/rollback_blog_urls.py` puts
them back. Drop `legacy` in v2.1.0.

    uv run python -m scripts.migrate_blog_urls
    uv run python -m scripts.migrate_blog_urls --apply
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from scripts._common import banner, base_parser, database, run, summarise

OLD_HOST = "blog.dileepa.dev"


def parse_date(value: Any) -> datetime | None:
    """v1 stored the publication date as free text. Read what is there."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def slug_date(slug: str) -> datetime | None:
    """Every slug starts with its date, which is a better source than the string field."""
    head = slug[:10]
    try:
        return datetime.strptime(head, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None


async def main(args: argparse.Namespace) -> int:
    banner("Rewrite blog URLs")
    settings = get_settings()
    site_url = args.site_url or settings.site_url
    counts = {"rows seen": 0, "rows rewritten": 0, "already migrated": 0, "no date found": 0}

    async with database(args) as db:
        async for row in db["blogs"].find({}).sort("slug", 1):
            counts["rows seen"] += 1
            slug = str(row.get("slug", ""))

            if "path" in row and "legacy" in row:
                counts["already migrated"] += 1
                continue

            path = f"/blog/{slug}"
            published = slug_date(slug) or parse_date(row.get("date"))
            if published is None:
                counts["no date found"] += 1
                print(f"  ! {slug}: no usable date. Set publishedDate by hand after this runs.")

            updates: dict[str, Any] = {
                "path": path,
                "canonicalUrl": f"{site_url.rstrip('/')}{path}",
                "description": row.get("description") or row.get("excerpt", ""),
                "draft": False,
                "featured": bool(row.get("featured", False)),
                "readingTimeMinutes": int(row.get("readingTimeMinutes", 0) or 0),
                "sourcePath": row.get("sourcePath") or f"content/posts/{slug}.mdx",
                "tags": list(row.get("tags", [])),
                "legacy": {
                    "link": row.get("link"),
                    "bannerUrl": row.get("bannerUrl"),
                    "date": row.get("date"),
                    "excerpt": row.get("excerpt"),
                },
            }
            if published is not None:
                updates["publishedDate"] = published

            banner_url = row.get("bannerUrl")
            if banner_url and OLD_HOST not in str(banner_url):
                # Already on a host that survives — Cloudinary or the old blob
                # store. Keep it; the image migration replaces it separately.
                updates["banner"] = {"url": banner_url, "alt": row.get("title", "")}
            elif banner_url:
                print(f"  ! {slug}: banner is on {OLD_HOST}. Re-upload it before applying.")

            print(f"  {slug}")
            print(f"      link       {row.get('link')!r}")
            print(f"   -> path       {path!r}")
            print(f"   -> canonical  {updates['canonicalUrl']!r}")
            if published is not None:
                print(f"   -> published  {published.date().isoformat()}")

            counts["rows rewritten"] += 1
            if args.apply:
                await db["blogs"].update_one(
                    {"_id": row["_id"]},
                    {"$set": updates, "$unset": {"link": "", "bannerUrl": ""}},
                )

    summarise(counts, apply=args.apply)
    return 0


if __name__ == "__main__":
    parser = base_parser(__doc__ or "")
    parser.add_argument("--site-url", default=None, help="Defaults to SITE_URL.")
    run(main, parser.parse_args())
