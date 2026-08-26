"""Create or update an admin account.

Users are seeded, not managed through the API — there is no `/users` resource.
This is how an account comes to exist.

    uv run python -m scripts.create_user --email owner@dileepa.dev --role admin --apply
"""

from __future__ import annotations

import argparse
import getpass
from datetime import UTC, datetime

from app.core.security import hash_password
from scripts._common import base_parser, database, run


async def main(args: argparse.Namespace) -> int:
    password = getpass.getpass("Password: ")
    if len(password) < 12:
        print("Use at least 12 characters.")
        return 1
    if password != getpass.getpass("Repeat: "):
        print("Those do not match.")
        return 1

    now = datetime.now(UTC)
    document = {
        "email": args.email,
        "passwordHash": hash_password(password),
        "roles": args.role,
        "isActive": True,
        "updatedAt": now,
    }

    async with database(args) as db:
        existing = await db["users"].find_one({"email": args.email})
        action = "update" if existing else "create"
        print(f"Would {action} {args.email} with roles {args.role}.")
        if not args.apply:
            print("Nothing written. Re-run with --apply.")
            return 0
        await db["users"].update_one(
            {"email": args.email},
            {"$set": document, "$setOnInsert": {"createdAt": now}},
            upsert=True,
        )
    print(f"Done — {args.email} can sign in.")
    return 0


if __name__ == "__main__":
    parser = base_parser(__doc__ or "")
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--role", action="append", default=None, help="Repeatable. Defaults to admin."
    )
    parsed = parser.parse_args()
    parsed.role = parsed.role or ["admin"]
    run(main, parsed)
