"""Auth and user models.

**Users are seeded, not managed through the API.** There is no `/users`
resource: v1 never had one either — `UsersService` only ever looked a user up by
email — and this is a single-owner platform. Exposing user CRUD would add attack
surface next to the password hashes for no benefit. Accounts are created with
`scripts/create_user.py`, run against the database directly. This closes the
`/users` question in `TODO.md`.

The sign-in response keeps v1's `access_token` field name so the admin app keeps
working across the cutover; `refresh_token` is new alongside it.
"""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.models.common import ApiModel, TimestampedResource


class SignInRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(ApiModel):
    refresh_token: str = Field(min_length=1, alias="refresh_token")


class TokenPair(ApiModel):
    # snake_case on purpose: v1 returned `access_token`, and the admin app reads
    # that name today. The camelCase alias generator is bypassed here.
    access_token: str = Field(serialization_alias="access_token")
    refresh_token: str = Field(serialization_alias="refresh_token")
    token_type: str = Field(default="bearer", serialization_alias="token_type")
    expires_in: int = Field(serialization_alias="expires_in")


class UserProfile(TimestampedResource):
    email: str
    roles: list[str] = Field(default_factory=list)
    is_active: bool = True


class AuthenticatedUser(ApiModel):
    """The caller, as reconstructed from a bearer token."""

    user_id: str
    email: str
    roles: list[str] = Field(default_factory=list)

    def has_role(self, *roles: str) -> bool:
        return any(role in self.roles for role in roles)
