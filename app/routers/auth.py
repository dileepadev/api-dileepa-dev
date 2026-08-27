"""Sign in, refresh, and who am I.

`POST /auth/login` is the contract's name and the only one. v1's
`POST /auth/sign-in` is gone: v2.0.0 ships as a single cutover, with every
consumer released at the same time, so there is no window in which an old path
needs to keep answering. The response still keeps v1's `access_token` field
name.

A successful sign-in against a legacy Node bcrypt hash rewrites that hash to
argon2id in place. The owner never sees it, and never has to reset a password.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.deps import CurrentUser, SettingsDep, repository
from app.core.errors import UnauthorizedError
from app.core.security import ACCESS, REFRESH, burn_timing, create_token, decode_token
from app.core.security import verify_and_upgrade_password as verify_password
from app.models.auth import RefreshRequest, SignInRequest, TokenPair, UserProfile
from app.repositories.base import DocumentRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

UsersRepo = Annotated[DocumentRepository, Depends(repository("users"))]


def _tokens(settings: Settings, *, user_id: str, email: str, roles: list[str]) -> TokenPair:
    return TokenPair(
        access_token=create_token(
            settings, subject=user_id, email=email, roles=roles, token_type=ACCESS
        ),
        refresh_token=create_token(
            settings, subject=user_id, email=email, roles=roles, token_type=REFRESH
        ),
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def _authenticate(
    payload: SignInRequest, settings: Settings, users: DocumentRepository
) -> TokenPair:
    user = await users.find_one({"email": payload.email})
    if user is None:
        # Spend the same work as a real verification so a wrong email is not
        # measurably faster than a wrong password.
        burn_timing()
        raise UnauthorizedError("That email and password do not match.", code="invalid_credentials")
    matched, upgraded_hash = verify_password(payload.password, str(user.get("passwordHash", "")))
    if not matched:
        raise UnauthorizedError("That email and password do not match.", code="invalid_credentials")

    # Checked *after* the password, not before. `account_disabled` says an
    # address is registered here, which is worth telling the person who owns
    # it and worth withholding from someone guessing addresses — and the
    # difference between the two is exactly whether they know the password.
    # Ordered the other way, the distinct code answered "is this email
    # registered?" for anyone who asked.
    if user.get("isActive") is False:
        raise UnauthorizedError(
            "That account is disabled. Ask the owner to re-enable it.", code="account_disabled"
        )

    if upgraded_hash:
        # Transparent migration off Node's bcrypt, one sign-in at a time.
        await users.update(str(user["_id"]), {"passwordHash": upgraded_hash})
        logger.info("Upgraded stored password hash for user %s", user["_id"])

    return _tokens(
        settings,
        user_id=str(user["_id"]),
        email=str(user["email"]),
        roles=list(user.get("roles", [])),
    )


@router.post("/login", response_model=TokenPair, summary="Sign in and get a token pair")
async def login(payload: SignInRequest, settings: SettingsDep, users: UsersRepo) -> TokenPair:
    """Exchange an email and password for an access and a refresh token."""
    return await _authenticate(payload, settings, users)


@router.post("/refresh", response_model=TokenPair, summary="Exchange a refresh token")
async def refresh(payload: RefreshRequest, settings: SettingsDep, users: UsersRepo) -> TokenPair:
    """Issue a new token pair from a refresh token.

    The user is re-read rather than trusted from the token, so a disabled
    account or a changed role takes effect at the next refresh instead of at the
    next sign-in.
    """
    claims = decode_token(settings, payload.refresh_token, expected_type=REFRESH)
    user = await users.get(str(claims["sub"]))
    if user is None:
        raise UnauthorizedError("That account no longer exists.", code="unknown_account")
    if user.get("isActive") is False:
        raise UnauthorizedError("That account is disabled.", code="account_disabled")
    return _tokens(
        settings,
        user_id=str(user["_id"]),
        email=str(user["email"]),
        roles=list(user.get("roles", [])),
    )


@router.get("/profile", response_model=UserProfile, summary="The signed-in user")
async def profile(user: CurrentUser, users: UsersRepo) -> UserProfile:
    """Return the current user, read fresh from the database."""
    record = await users.get(user.user_id)
    if record is None:
        raise UnauthorizedError("That account no longer exists.", code="unknown_account")
    return UserProfile.model_validate(record)
