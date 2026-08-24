"""Password hashing and JWTs.

Two constraints shaped this file, both cutover risks rather than preferences:

1. **Existing password hashes were produced by Node's `bcrypt`.** They are
   verified here as-is. `pwdlib` is configured with argon2id first and bcrypt
   second, so a legacy `$2a$`/`$2b$` hash still validates and gets rewritten to
   argon2id on the owner's next successful sign-in. No forced password reset.

   `pwdlib` is used rather than `passlib`, which `AGENTS.md` originally named:
   passlib has been unmaintained since 2020 and breaks against bcrypt >= 4.1.
   `pwdlib` is what the FastAPI security documentation now uses, and it verifies
   the same hashes. Verified against real Node `bcrypt` output at rounds 10 and
   12, both `$2a$` and `$2b$` — see `scripts/verify_password_hash.py`.

2. **Tokens minted by the NestJS app must keep working through the cutover.**
   The algorithm, secret, lifetime and claim names (`sub`, `email`, `roles`) are
   unchanged. `type` is new, so a token without one is read as an access token.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import Settings
from app.core.errors import UnauthorizedError

TokenType = Literal["access", "refresh"]

ACCESS: TokenType = "access"
REFRESH: TokenType = "refresh"

# Order matters: the first hasher is used for new hashes, the rest only verify.
_password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))

# Verifying a throwaway hash on a missing user keeps sign-in timing roughly
# constant, so a wrong email is not measurably faster than a wrong password.
_DUMMY_HASH = _password_hash.hash("timing-equalisation-only")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hash.verify(password, password_hash)
    except (UnknownHashError, ValueError, TypeError):
        # A stored hash this build cannot read is a failed sign-in, not a 500.
        return False


def verify_and_upgrade_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Verify a password and return a rehash when the stored one is outdated.

    The second element is a new argon2id hash when the stored hash was bcrypt,
    and `None` when nothing needs rewriting.
    """
    try:
        return _password_hash.verify_and_update(password, password_hash)
    except (UnknownHashError, ValueError, TypeError):
        # An unrecognised or corrupt hash is a failed verification, not a 500.
        return False, None


def burn_timing() -> None:
    """Spend the same work as a real verification, for a user that does not exist."""
    _password_hash.verify("timing-equalisation-only", _DUMMY_HASH)


def create_token(
    settings: Settings,
    *,
    subject: str,
    email: str,
    roles: list[str],
    token_type: TokenType,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = (
            timedelta(minutes=settings.access_token_expire_minutes)
            if token_type == ACCESS
            else timedelta(days=settings.refresh_token_expire_days)
        )
    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "roles": roles,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(settings: Settings, token: str, *, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError(
            "That session has expired. Sign in again.", code="token_expired"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(
            "That token is not valid for this API.", code="token_invalid"
        ) from exc

    # Tokens issued by the NestJS app carry no `type`. Read those as access
    # tokens so live sessions survive the cutover; remove this in v2.1.0, once
    # every v1 token has expired.
    actual_type = payload.get("type", ACCESS)
    if actual_type != expected_type:
        raise UnauthorizedError(
            f"This endpoint needs a {expected_type} token, not a {actual_type} token.",
            code="token_wrong_type",
        )
    if not payload.get("sub"):
        raise UnauthorizedError("That token has no subject claim.", code="token_invalid")
    return payload
