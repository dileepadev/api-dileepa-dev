"""Check a real password hash from the database before the auth cutover.

This is the one check that has to pass before anything else in the migration
matters. Existing hashes were written by Node's `bcrypt`. If they do not
validate here, signing in against FastAPI locks the owner out of their own
admin.

    uv run python -m scripts.verify_password_hash --email owner@dileepa.dev

The password is read from a prompt, never from an argument, so it does not land
in shell history. Nothing is written: this is read-only even with `--apply`
absent, because there is no write path at all.
"""

from __future__ import annotations

import argparse
import getpass

from app.core.security import verify_and_upgrade_password, verify_password
from scripts._common import base_parser, database, run


async def main(args: argparse.Namespace) -> int:
    async with database(args) as db:
        user = await db["users"].find_one({"email": args.email})

    if user is None:
        print(f"No user with email {args.email!r}. Check the address and the database.")
        return 1

    stored = str(user.get("passwordHash", ""))
    if not stored:
        print(f"{args.email} has no passwordHash field. Nothing to verify.")
        return 1

    scheme = stored.split("$")[1] if stored.startswith("$") else "unknown"
    print(f"User:   {args.email}")
    print(f"Active: {user.get('isActive', True)}")
    print(f"Roles:  {user.get('roles', [])}")
    print(f"Hash:   ${scheme}$… ({len(stored)} characters)")

    password = getpass.getpass("Password for that account: ")
    if not password:
        print("No password entered.")
        return 1

    if not verify_password(password, stored):
        print(
            "\nFAILED — that password does not validate against the stored hash.\n"
            "Either the password is wrong, or the hash cannot be read by this build.\n"
            "Do not cut over until this passes. The fallback is a planned password\n"
            "reset with a working recovery path, documented in CHANGELOG.md."
        )
        return 1

    _, upgraded = verify_and_upgrade_password(password, stored)
    print("\nPASSED — the stored hash validates.")
    if upgraded:
        print(
            "The hash is a legacy bcrypt one. It will be rewritten to argon2id\n"
            "automatically on the next successful sign-in. No reset is needed."
        )
    else:
        print("The hash is already in the current scheme.")
    return 0


if __name__ == "__main__":
    parser = base_parser(__doc__ or "")
    parser.add_argument("--email", required=True, help="The account to check.")
    run(main, parser.parse_args())
