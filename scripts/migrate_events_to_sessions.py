"""Convert `events` documents into the `sessions` shape.

`events` is not renamed: it is read, converted, and written to a separate
`sessions` collection, leaving the original rows untouched. `GET /events` keeps
working throughout because it projects sessions back into the v1 shape.

v1 stored seven fields, and three of them need judgement:

- `date` was free text. Parsed here; anything unparseable is reported and
  skipped rather than guessed at.
- `format` was a label like "In-Person". Mapped to the enum.
- there was no slug. One is derived from the title and the date, and collisions
  are reported rather than silently suffixed.

    uv run python -m scripts.migrate_events_to_sessions
    uv run python -m scripts.migrate_events_to_sessions --apply
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
        "event": None,
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
        "meta": {"migratedFromEventId": str(event["_id"])},
    }


async def main(args: argparse.Namespace) -> int:
    banner("Convert events into sessions")
    counts = {"events seen": 0, "converted": 0, "unparseable date": 0, "slug already taken": 0}

    async with database(args) as db:
        async for event in db["events"].find({}).sort("index", -1):
            counts["events seen"] += 1
            session = convert(event, timezone=args.timezone)
            if session is None:
                counts["unparseable date"] += 1
                print(
                    f"  ! {event.get('title')!r}: date {event.get('date')!r} could not be read. "
                    "Convert this one by hand."
                )
                continue

            clash = await db["sessions"].find_one({"slug": session["slug"]})
            if clash is not None:
                counts["slug already taken"] += 1
                print(f"  ! {session['slug']}: a session with that slug already exists. Skipped.")
                continue

            print(f"  {event.get('title')!r} -> {session['slug']}  ({session['format']})")
            counts["converted"] += 1
            if args.apply:
                now = datetime.now(UTC)
                await db["sessions"].insert_one({**session, "createdAt": now, "updatedAt": now})

    summarise(counts, apply=args.apply)
    if not args.apply:
        print("The `events` collection is never modified. Re-running is safe.")
    return 0


if __name__ == "__main__":
    parser = base_parser(__doc__ or "")
    parser.add_argument(
        "--timezone", default="Asia/Colombo", help="IANA timezone for the converted sessions."
    )
    run(main, parser.parse_args())
