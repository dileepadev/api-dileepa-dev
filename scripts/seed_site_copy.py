"""Seed `pillars`, `speaking_topics`, and the two speaker bios on `about`.

All three shipped empty, and all three replace copy that was compiled into
`dileepa-dev`. Until this has run, the website falls back to the constants it
still carries — so nothing breaks before it, and nothing is duplicated after it.
The records below are those constants, moved rather than rewritten: this script
is the cutover, not an edit.

Idempotent by `title`, which is what a person recognises a card by and the only
stable key either collection has. An existing row is updated in place, keeping
its `_id`, its `createdAt` and any ordering the admin has since given it — so a
second run repairs drift rather than duplicating, and re-running after editing
a record here pushes that edit through.

The two bios are written to `about` **only if that record has neither**, unlike
the collections above. A bio is a paragraph someone may well have already
rewritten from the admin, and overwriting an approved biography with a default
is not something a re-run should be able to do by accident.

    uv run python -m scripts.seed_site_copy              # dry run
    uv run python -m scripts.seed_site_copy --apply      # write
"""

from __future__ import annotations

import argparse
from typing import Any

from app.models.profile import PillarCreate, SpeakingTopicCreate
from app.repositories.base import utc_now
from scripts._common import banner, base_parser, database, run, summarise

# Higher `order` sorts first — `DEFAULT_SORT` is ("order", -1). Spaced by ten so
# a row can be slid between two others from the admin without renumbering.
PILLARS: list[dict[str, Any]] = [
    {
        "title": "AI engineering",
        "description": (
            "Building agentic systems, orchestrating LLM workflows, and designing "
            "evaluation pipelines for production applications."
        ),
        "icon": "cpu",
        "order": 60,
    },
    {
        "title": "Open source",
        "description": (
            "Developing tools, contributing to projects, and sharing technical "
            "implementations across AI and software engineering."
        ),
        "icon": "code",
        "order": 50,
    },
    {
        "title": "Public speaking",
        "description": (
            "Speaking at conferences and meetups, leading technical workshops, and "
            "sharing lessons from building AI systems."
        ),
        "icon": "mic",
        "order": 40,
    },
    {
        "title": "Technical writing",
        "description": (
            "Writing about agentic systems, engineering practices, and lessons from "
            "building AI in production."
        ),
        "icon": "book",
        "order": 30,
    },
    {
        "title": "Technical videos",
        "description": (
            "Creating technical tutorials and walkthroughs on AI systems, software "
            "engineering, and cloud infrastructure."
        ),
        "icon": "video",
        "order": 20,
    },
    {
        "title": "Community building",
        "description": (
            "Organising technical meetups, mentoring engineers, and creating spaces "
            "for people and AI agents to learn and build."
        ),
        "icon": "users",
        "order": 10,
    },
]

SPEAKING_TOPICS: list[dict[str, Any]] = [
    {
        "title": "Building production AI agents & multi-agent frameworks",
        "summary": (
            "Architecting autonomous agent systems, multi-agent orchestration, tool "
            "routing, and designing evaluation loops that hold up under real-world traffic."
        ),
        "order": 40,
    },
    {
        "title": "Production LLM pipelines & evaluation harnesses",
        "summary": (
            "Tracing, debugging, and benchmarking LLM applications. Moving from "
            "experimental prompts to reliable systems with measurable performance."
        ),
        "order": 30,
    },
    {
        "title": "Azure AI Foundry & enterprise AI architecture",
        "summary": (
            "Leveraging managed AI platforms for enterprise security, model governance, "
            "data isolation, and scalable agent deployment."
        ),
        "order": 20,
    },
    {
        "title": "Open source AI engineering & community building",
        "summary": (
            "Practical strategies for creating developer tooling, building transparent "
            "software, and cultivating high-impact engineering communities."
        ),
        "order": 10,
    },
]

SHORT_BIO = (
    "Dileepa Bandara is an AI engineer building agentic systems, production LLM "
    "pipelines, and the developer communities around them. He speaks and leads "
    "technical workshops on AI architectures, multi-agent orchestration, and cloud "
    "infrastructure."
)

FULL_BIO = (
    "Dileepa Bandara is an AI systems engineer with experience building agentic "
    "applications, production evaluation harnesses, and scalable cloud solutions. A "
    "community builder and active technical speaker, Dileepa has delivered numerous "
    "talks and hands-on workshops across developer meetups, conferences, and "
    "open-source groups. He focuses on practical AI engineering — moving beyond basic "
    "prototypes to resilient, observable production systems. Dileepa writes about AI "
    "architecture on dileepa.dev and maintains open-source tools for developers."
)


async def _seed(
    db: Any,
    *,
    collection_name: str,
    documents: list[dict[str, Any]],
    apply: bool,
    counts: dict[str, int],
) -> None:
    collection = db[collection_name]

    for document in documents:
        title = document["title"]
        existing = await collection.find_one({"title": title})
        action = "update" if existing else "create"
        print(f"  {action:7} {collection_name:16} {title}")

        if not apply:
            counts[f"{collection_name} written"] += 1
            continue

        now = utc_now()
        if existing is None:
            await collection.insert_one({**document, "createdAt": now, "updatedAt": now})
        else:
            # `createdAt` and `_id` are left alone: this repairs a record, it
            # does not replace it, and the admin may have reordered it since.
            await collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {**document, "updatedAt": now}},
            )
        counts[f"{collection_name} written"] += 1


async def main(args: argparse.Namespace) -> int:
    banner("Seed site copy")

    # Validated before the database is opened. A record the API would refuse
    # should fail here, where nothing has been written, rather than halfway
    # through the list.
    pillars = [PillarCreate.model_validate(r).model_dump(by_alias=True) for r in PILLARS]
    topics = [
        SpeakingTopicCreate.model_validate(r).model_dump(by_alias=True) for r in SPEAKING_TOPICS
    ]

    counts = {"pillars written": 0, "speaking_topics written": 0, "bios written": 0}

    async with database(args) as db:
        await _seed(
            db, collection_name="pillars", documents=pillars, apply=args.apply, counts=counts
        )
        await _seed(
            db,
            collection_name="speaking_topics",
            documents=topics,
            apply=args.apply,
            counts=counts,
        )

        about = await db["about"].find_one({})
        if about is None:
            print("\n  skip    about            no about record exists yet, so no bios written")
        elif about.get("shortBio") or about.get("fullBio"):
            print("\n  skip    about            a biography is already set; left untouched")
        else:
            print("\n  update  about            shortBio, fullBio")
            counts["bios written"] = 2
            if args.apply:
                await db["about"].update_one(
                    {"_id": about["_id"]},
                    {
                        "$set": {
                            "shortBio": SHORT_BIO,
                            "fullBio": FULL_BIO,
                            "updatedAt": utc_now(),
                        }
                    },
                )

        print(
            f"\n  pillars in the collection now:         {await db['pillars'].count_documents({})}"
        )
        print(
            "  speaking topics in the collection now: "
            f"{await db['speaking_topics'].count_documents({})}"
        )

    summarise(counts, apply=args.apply)
    return 0


if __name__ == "__main__":
    parser = base_parser(__doc__ or "Seed the site-copy collections.")
    run(main, parser.parse_args())
