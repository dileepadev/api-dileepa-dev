"""Rewrite the v1 `events` documents into the v2 `events` shape, in place.

The collection keeps its name — `events` is what v2 serves — so this rewrites
rows rather than moving them. **Every original is copied to `events_v1_backup`
first**, and the copy carries its original `_id`, so restoring is a straight
copy back:

    db.events_v1_backup.aggregate([{ $out: "events" }])

v1 stored seven fields, and three of them need judgement:

- `date` was free text. Parsed here; anything unparseable is reported and
  skipped rather than guessed at.
- `format` was a label like "In-Person". Mapped to the enum.
- there was no slug. One is derived from the title and the date, and collisions
  are reported rather than silently suffixed.

Rewriting preserves `_id`, so the script is idempotent: a row already in the v2
shape is recognised and left alone.

    uv run python -m scripts.migrate_events_v1_to_v2
    uv run python -m scripts.migrate_events_v1_to_v2 --apply
"""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from typing import Any

from scripts._common import banner, base_parser, database, run, summarise

FORMATS = {
    "in-person": "in_person",
    "in person": "in_person",
    "inperson": "in_person",
    "physical": "in_person",
    "online": "online",
    "virtual": "online",
    "remote": "online",
    "hybrid": "hybrid",
}

DATE_FORMATS = ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d/%m/%Y", "%Y/%m/%d")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def convert(event: dict[str, Any], *, timezone: str) -> dict[str, Any] | None:
    start_at = parse_date(event.get("date"))
    if start_at is None:
        return None

    title = str(event.get("title", "")).strip()
    slug = f"{start_at.date().isoformat()}-{slugify(title)}"[:140].rstrip("-")

    location_text = str(event.get("location", "")).strip()
    event_format = FORMATS.get(str(event.get("format", "")).strip().lower(), "in_person")
    location = None
    if event_format != "online" and location_text:
        # v1 stored one free-text line. Keep it as the venue rather than
        # guessing at a city and country split.
        location = {"venue": location_text, "city": None, "country": None, "mapUrl": None}

    links = []
    url = str(event.get("url", "")).strip()
    if url:
        links.append({"label": "Event page", "url": url, "kind": "announcement"})

    description = str(event.get("description", "")).strip()
    return {
        "slug": slug,
        "title": title,
        "summary": description[:200],
        "description": description,
        "type": "other",
        "format": event_format,
        "startAt": start_at,
        "endAt": None,
        "timezone": timezone,
        # Left unset so the API derives it from startAt.
        "location": location,
        "host": None,
        "speakers": [],
        "cover": None,
        "photos": [],
        "recordings": [],
        "slides": None,
        "links": links,
        "tags": [],
        "series": None,
        "audienceSize": None,
        # Present, not missing: MongoDB sorts an absent field below `false`.
        "featured": False,
        "order": int(event.get("order", event.get("index", 0)) or 0),
        "published": True,
        "seo": {"metaTitle": None, "metaDescription": None, "ogImage": None},
        "meta": {"migratedFrom": "events-v1"},
    }


BACKUP = "events_v1_backup"


def is_v2(document: dict[str, Any]) -> bool:
    """A v2 row has a slug and a real datetime start. A v1 row has neither."""
    return isinstance(document.get("slug"), str) and isinstance(document.get("startAt"), datetime)


async def main(args: argparse.Namespace) -> int:
    banner("Rewrite v1 events into the v2 shape")
    counts = {
        "events seen": 0,
        "already v2": 0,
        "converted": 0,
        "unparseable date": 0,
        "slug already taken": 0,
        "backed up": 0,
    }
    slugs_seen: set[str] = set()

    async with database(args) as db:
        originals = [doc async for doc in db["events"].find({}).sort("index", 1)]
        pending = [doc for doc in originals if not is_v2(doc)]
        counts["events seen"] = len(originals)
        counts["already v2"] = len(originals) - len(pending)

        if pending:
            existing_backup = await db[BACKUP].count_documents({})
            if existing_backup:
                print(
                    f"  {BACKUP} already holds {existing_backup} documents; "
                    "leaving it as it is rather than overwriting an earlier backup."
                )
            else:
                print(f"  Backing up {len(pending)} v1 documents to {BACKUP}.")
                counts["backed up"] = len(pending)
                if args.apply:
                    await db[BACKUP].insert_many([dict(doc) for doc in pending])

        # Slugs that already exist on rows this run will not touch.
        for doc in originals:
            if is_v2(doc) and isinstance(doc.get("slug"), str):
                slugs_seen.add(doc["slug"])

        for event in pending:
            converted = convert(event, timezone=args.timezone)
            if converted is None:
                counts["unparseable date"] += 1
                print(
                    f"  ! {event.get('title')!r}: date {event.get('date')!r} could not be read. "
                    "Convert this one by hand."
                )
                continue

            if converted["slug"] in slugs_seen:
                counts["slug already taken"] += 1
                print(f"  ! {converted['slug']}: that slug is already taken. Skipped.")
                continue
            slugs_seen.add(converted["slug"])

            print(f"  {event.get('title')!r} -> {converted['slug']}  ({converted['format']})")
            counts["converted"] += 1
            if args.apply:
                now = datetime.now(UTC)
                stored = event.get("createdAt")
                created = stored if isinstance(stored, datetime) else now
                # replace_one, not update: the v1 fields (date, location, index,
                # __v) must go, or they sit alongside the v2 ones forever.
                await db["events"].replace_one(
                    {"_id": event["_id"]},
                    {**converted, "createdAt": created, "updatedAt": now},
                )

    summarise(counts, apply=args.apply)
    if not args.apply:
        print(f"Nothing was written, and {BACKUP} was not created.")
    else:
        print(f"\nOriginals are in {BACKUP}. To undo:")
        print(f'  db.{BACKUP}.aggregate([{{ $out: "events" }}])')
    return 0


if __name__ == "__main__":
    parser = base_parser(__doc__ or "")
    parser.add_argument(
        "--timezone", default="Asia/Colombo", help="IANA timezone for the converted events."
    )
    run(main, parser.parse_args())
