"""Seed the `projects` collection.

`/projects` was net-new in v2.0.0 and shipped with nothing in it, so the site
served its empty state. This is the initial set, written once and then owned by
the admin like every other collection.

**The records below are the reviewable part.** Every field is drawn from the
repository it describes — its README, its description, its actual contents —
rather than written to flatter. `status` in particular is read off what is
committed: three of these are a README and a licence with no code behind them
yet, and they say `concept` because that is what they are. A project page that
calls a plan "active" is a page that lies to the one reader who clicks through
to the repository.

Idempotent by `slug`: an existing project is updated in place, keeping its
`_id`, its `createdAt` and any ordering the admin has since given it. So a
second run repairs drift rather than duplicating, and re-running after editing
a record here pushes that edit through.

    uv run python -m scripts.seed_projects              # dry run
    uv run python -m scripts.seed_projects --apply      # write
"""

from __future__ import annotations

import argparse
from typing import Any

from app.models.project import ProjectCreate
from app.repositories.base import utc_now
from scripts._common import banner, base_parser, database, run, summarise

# Higher `order` sorts first — `DEFAULT_SORT` is ("order", -1). Spaced by ten so
# a project can be slid between two others from the admin without renumbering.
PROJECTS: list[dict[str, Any]] = [
    {
        "slug": "microsoft-agent-framework-workshop",
        "name": "Microsoft Agent Framework Workshop",
        "tagline": "One agent core. Swap the model, swap the surface, swap the host.",
        "description": (
            "A 60-minute hands-on workshop for building AI agents and multi-agent workflows "
            "with Microsoft Agent Framework. Participants build OpsAgent, an operations "
            "assistant, against a single agent core that stays put while the model, the "
            "interface and the host all change around it.\n\n"
            "GitHub Models was retired on 30 July 2026 and took the v1.0 lab with it — the "
            "whole edition ran against an inference endpoint that no longer exists. v2.0 is a "
            "rebuild rather than an upgrade, and losing a provider overnight became the lesson "
            "of the session rather than an interruption to it.\n\n"
            "Each folder carries its own isolated environment, so one broken install cannot "
            "take down the rest of the workshop."
        ),
        "status": "active",
        "role": "Author and facilitator",
        "stack": ["Microsoft Agent Framework", "Python", "uv", "MCP", "Astro"],
        "categories": ["AI engineering", "Workshop"],
        "tags": ["agents", "microsoft-agent-framework", "mcp", "workshop", "teaching"],
        "links": {
            "repo": "https://github.com/dileepadev/microsoft-agent-framework-workshop",
            "demo": "https://dileepadev.github.io/microsoft-agent-framework-workshop/",
        },
        "highlights": [
            "One agent core, with the model, the surface and the host each swappable",
            "Rebuilt as v2.0 after GitHub Models was retired in July 2026",
            "Per-folder isolated environments, so one broken install cannot stop the session",
        ],
        "featured": True,
        "order": 70,
    },
    {
        "slug": "ml-dataset-health-api",
        "name": "ML Dataset Health API",
        "tagline": "Find the problems in a dataset before a pipeline does.",
        "description": (
            "A FastAPI service that profiles CSV and JSON datasets and returns a "
            "machine-readable data quality and ML readiness report.\n\n"
            "It checks the things that quietly ruin a training run: missing values, duplicate "
            "rows, wrong data types, outliers and feature correlation. The output is a health "
            "score and a set of readiness insights, so a dataset can be rejected at the door "
            "rather than halfway through a pipeline."
        ),
        "status": "active",
        "role": "Author",
        "stack": ["Python", "FastAPI", "uv", "pandas"],
        "categories": ["AI engineering", "API"],
        "tags": ["ml", "data-quality", "fastapi", "profiling"],
        "links": {"repo": "https://github.com/dileepadev/ml-dataset-health-api"},
        "highlights": [
            "Profiling, missing values, duplicates, type analysis and outlier detection",
            "A single health score plus ML readiness insights, not a wall of statistics",
            "Bundled sample datasets, so it can be tried without supplying data",
        ],
        "featured": True,
        "order": 60,
    },
    {
        "slug": "mender",
        "name": "Mender",
        "tagline": "CI that fixes itself, and proves the fix.",
        "description": (
            "Mender watches a pipeline, reproduces failures in a sandbox, diagnoses the root "
            "cause, and opens a pull request containing both the fix and the regression test "
            "that proves it. When it cannot prove a fix, it opens an issue with its diagnosis "
            "instead of guessing.\n\n"
            "The distinction it is built around is suggestion versus verified outcome. Wiring "
            "a model to a stack trace is easy; proving the fix works — and declining to open a "
            "pull request when it does not — is the engineering.\n\n"
            "Early development. The loop and the safety model are settled and written down; "
            "the implementation is not built yet."
        ),
        "status": "concept",
        "role": "Author",
        "stack": ["Python", "GitHub Actions"],
        "categories": ["AI engineering", "Developer tooling"],
        "tags": ["agents", "ci", "automation", "testing"],
        "links": {"repo": "https://github.com/dileepadev/mender"},
        "highlights": [
            "Reproduces a failure in a sandbox before attempting any fix",
            "Opens an issue with its diagnosis when it cannot prove a fix",
            "Every pull request carries the patch, the regression test and before/after logs",
        ],
        "featured": False,
        "order": 50,
    },
    {
        "slug": "qa-test-pilot",
        "name": "QATestPilot",
        "tagline": "Give it an API. Let the agent test it.",
        "description": (
            "An autonomous QA agent that analyses an API, generates test scenarios, runs them, "
            "investigates the failures and produces a structured report.\n\n"
            "The intent is the decision-making rather than the execution: working out what to "
            "test, how to test it, and what the results mean, instead of running a suite "
            "somebody else already wrote.\n\n"
            "Early: the design is written down and the implementation has not started."
        ),
        "status": "concept",
        "role": "Author",
        "stack": ["Python"],
        "categories": ["AI engineering", "Developer tooling"],
        "tags": ["agents", "qa", "api-testing", "automation"],
        "links": {"repo": "https://github.com/dileepadev/qa-test-pilot"},
        "highlights": [
            "The agent chooses the test scenarios rather than executing a written suite",
            "Failure analysis is part of the loop, not a separate reading of the logs",
        ],
        "featured": False,
        "order": 40,
    },
    {
        "slug": "microsoft-agent-framework-chat-app",
        "name": "Microsoft Agent Framework Chat App",
        "tagline": "A chat surface for an agent that remembers, calls tools and speaks MCP.",
        "description": (
            "A chat application built on Microsoft Agent Framework, covering the parts of an "
            "agent that only show up once there is a conversation in front of it: memory "
            "across turns, tool calling, and Model Context Protocol integration.\n\n"
            "Written as a companion to the workshop — the same framework, arranged as an "
            "application rather than a lesson.\n\n"
            "The design is documented and the implementation is not committed yet."
        ),
        "status": "concept",
        "role": "Author",
        "stack": ["Python", "Microsoft Agent Framework", "MCP", "Chainlit", "uv"],
        "categories": ["AI engineering"],
        "tags": ["agents", "microsoft-agent-framework", "mcp", "tool-calling", "chat"],
        "links": {"repo": "https://github.com/dileepadev/microsoft-agent-framework-chat-app"},
        "highlights": [
            "Conversation memory carried across turns",
            "Tool calling and MCP integration in one surface",
        ],
        "featured": False,
        "order": 30,
    },
    {
        "slug": "trashpick",
        "name": "TrashPick",
        "tagline": "A Flutter app for sorting waste, and for the people who collect it.",
        "description": (
            "A mobile app that guides people on disposing of waste properly. A user registers "
            "as a trash picker or a trash collector: pickers post what they have and can sell "
            "it on, collectors buy it and pass it to recycling centres, and both earn points "
            "toward rewards.\n\n"
            "Built as an open source educational project and released in July 2021. The "
            "repository is a clean re-upload to this account, so the original commit history "
            "is not preserved."
        ),
        "status": "archived",
        "role": "Author",
        "stack": ["Flutter", "Dart", "Firebase"],
        "categories": ["Mobile"],
        "tags": ["flutter", "firebase", "mobile", "sustainability"],
        "links": {
            "repo": "https://github.com/dileepadev/trashpick",
            "demo": "https://youtu.be/lwqs8Z3Aw50",
        },
        "highlights": [
            "Two roles in one app — trash pickers and trash collectors",
            "Points and rewards to keep both sides using it",
        ],
        "featured": False,
        "order": 20,
    },
    {
        "slug": "railway-guider",
        "name": "Railway Guider",
        "tagline": "Booking, QR tickets and live train locations, across four applications.",
        "description": (
            "A railway system built as four separate applications: a passenger mobile app, an "
            "admin mobile app, a ticket scanner and a web front end. Passengers book a train, "
            "view and generate QR tickets, follow the location of a booked train, and earn "
            "loyalty points through gift cards.\n\n"
            "Built as an open source educational project and first released in July 2020. The "
            "repository is a clean re-upload to this account, so the original commit history "
            "is not preserved."
        ),
        "status": "archived",
        "role": "Author",
        "stack": ["Java", "Android", "C#", "Firebase"],
        "categories": ["Mobile"],
        "tags": ["android", "java", "mobile", "railway", "qr"],
        "links": {
            "repo": "https://github.com/dileepadev/railway-guider",
            "demo": "https://youtu.be/M0syZuBxhbY",
        },
        "highlights": [
            "Four applications — passenger app, admin app, ticket scanner and web",
            "QR ticket generation and live train location for booked journeys",
        ],
        "featured": False,
        "order": 10,
    },
]


async def main(args: argparse.Namespace) -> int:
    banner("Seed projects")

    # Validated before the database is opened. A record that the API would
    # refuse should fail here, where nothing has been written, rather than
    # halfway through the list.
    validated = [ProjectCreate.model_validate(record) for record in PROJECTS]
    documents = [record.model_dump(by_alias=True) for record in validated]

    async with database(args) as db:
        collection = db["projects"]
        counts = {"created": 0, "updated": 0, "unchanged": 0}

        for document in documents:
            slug = document["slug"]
            existing = await collection.find_one({"slug": slug})
            action = "update" if existing else "create"

            status = document["status"]
            published = "published" if document["published"] else "unpublished"
            print(f"  {action:7} {slug:42} {status:10} {published}")

            if not args.apply:
                counts["created" if action == "create" else "updated"] += 1
                continue

            now = utc_now()
            if existing is None:
                await collection.insert_one({**document, "createdAt": now, "updatedAt": now})
                counts["created"] += 1
            else:
                # `createdAt` and `_id` are left alone: this repairs a record, it
                # does not replace it, and the admin may have reordered it since.
                await collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {**document, "updatedAt": now}},
                )
                counts["updated"] += 1

        total = await collection.count_documents({})
        print(f"\n  projects in the collection now: {total}")

    summarise(counts, apply=args.apply)
    return 0


if __name__ == "__main__":
    parser = base_parser(__doc__ or "Seed the projects collection.")
    run(main, parser.parse_args())
