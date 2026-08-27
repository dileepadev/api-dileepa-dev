"""Auth — the highest cutover risk in the migration.

`AGENTS.md`: "test token issue, refresh, expiry, and role enforcement
explicitly, not incidentally". That is what this file does.
"""

from __future__ import annotations

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.security import verify_password
from tests.conftest import (
    ADMIN_ID,
    NODE_BCRYPT_HASH,
    NODE_BCRYPT_PASSWORD,
    expired_token,
    token_for,
)
from tests.types import Headers, Repos


class TestLegacyPasswordHashes:
    """The load-bearing check: Node's bcrypt output must still validate."""

    def test_node_bcrypt_hash_verifies(self) -> None:
        assert verify_password(NODE_BCRYPT_PASSWORD, NODE_BCRYPT_HASH)

    def test_node_bcrypt_hash_rejects_wrong_password(self) -> None:
        assert not verify_password("not-the-password", NODE_BCRYPT_HASH)

    def test_2a_prefix_also_verifies(self) -> None:
        # Older rows may carry the $2a$ prefix rather than $2b$.
        legacy = NODE_BCRYPT_HASH.replace("$2b$", "$2a$", 1)
        assert verify_password(NODE_BCRYPT_PASSWORD, legacy)

    def test_corrupt_hash_is_a_failed_login_not_a_crash(self) -> None:
        assert not verify_password(NODE_BCRYPT_PASSWORD, "not-a-hash")

    async def test_sign_in_rewrites_a_bcrypt_hash_to_argon2(
        self, client: AsyncClient, repositories: Repos
    ) -> None:
        """The owner signs in with their existing password and never notices."""
        response = await client.post(
            "/auth/login",
            json={"email": "owner@dileepa.dev", "password": NODE_BCRYPT_PASSWORD},
        )
        assert response.status_code == 200

        stored = await repositories["users"].get(str(ADMIN_ID))
        assert stored is not None
        assert stored["passwordHash"].startswith("$argon2id$")
        # And the new hash still authenticates the same password.
        again = await client.post(
            "/auth/login",
            json={"email": "owner@dileepa.dev", "password": NODE_BCRYPT_PASSWORD},
        )
        assert again.status_code == 200


class TestSignIn:
    async def test_returns_v1_field_names(self, client: AsyncClient) -> None:
        response = await client.post(
            "/auth/login",
            json={"email": "owner@dileepa.dev", "password": NODE_BCRYPT_PASSWORD},
        )
        body = response.json()
        # The admin app reads `access_token` today. Renaming it would sign the
        # owner out at cutover.
        assert set(body) == {"access_token", "refresh_token", "token_type", "expires_in"}
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 60 * 60

    async def test_claims_match_v1(self, client: AsyncClient) -> None:
        response = await client.post(
            "/auth/login",
            json={"email": "owner@dileepa.dev", "password": NODE_BCRYPT_PASSWORD},
        )
        settings = get_settings()
        claims = jwt.decode(
            response.json()["access_token"],
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        assert claims["sub"] == str(ADMIN_ID)
        assert claims["email"] == "owner@dileepa.dev"
        assert claims["roles"] == ["admin"]
        assert claims["type"] == "access"

    @pytest.mark.parametrize(
        ("email", "password", "code"),
        [
            ("owner@dileepa.dev", "wrong", "invalid_credentials"),
            ("nobody@dileepa.dev", "whatever", "invalid_credentials"),
            ("disabled@dileepa.dev", "disabled-password", "account_disabled"),
            # A wrong password on a disabled account must be indistinguishable
            # from a wrong password anywhere else. `account_disabled` confirms
            # the address is registered here, so it is only safe to return to
            # someone who has already proved they own it.
            ("disabled@dileepa.dev", "wrong", "invalid_credentials"),
        ],
    )
    async def test_rejections(
        self, client: AsyncClient, email: str, password: str, code: str
    ) -> None:
        response = await client.post("/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == code

    async def test_unknown_email_and_wrong_password_are_indistinguishable(
        self, client: AsyncClient
    ) -> None:
        missing = await client.post(
            "/auth/login", json={"email": "nobody@dileepa.dev", "password": "x"}
        )
        wrong = await client.post(
            "/auth/login", json={"email": "owner@dileepa.dev", "password": "x"}
        )
        assert missing.json() == wrong.json()

    async def test_the_v1_path_is_gone(self, client: AsyncClient) -> None:
        # v1's /auth/sign-in is not aliased. The admin app moves to /auth/login
        # in the same release, so a 404 here is the intended answer, not a gap.
        response = await client.post(
            "/auth/sign-in",
            json={"email": "owner@dileepa.dev", "password": NODE_BCRYPT_PASSWORD},
        )
        assert response.status_code == 404


class TestTokens:
    async def test_refresh_issues_a_new_pair(self, client: AsyncClient, refresh_token: str) -> None:
        response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        assert response.json()["access_token"]

    async def test_an_access_token_cannot_be_used_to_refresh(
        self, client: AsyncClient, admin_token: str
    ) -> None:
        response = await client.post("/auth/refresh", json={"refresh_token": admin_token})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "token_wrong_type"

    async def test_a_refresh_token_cannot_authorise_a_request(
        self, client: AsyncClient, refresh_token: str
    ) -> None:
        response = await client.get(
            "/auth/profile", headers={"Authorization": f"Bearer {refresh_token}"}
        )
        assert response.status_code == 401

    async def test_expired_token_is_rejected(self, client: AsyncClient) -> None:
        response = await client.get(
            "/auth/profile", headers={"Authorization": f"Bearer {expired_token()}"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "token_expired"

    async def test_token_signed_with_another_secret_is_rejected(self, client: AsyncClient) -> None:
        forged = jwt.encode({"sub": str(ADMIN_ID), "roles": ["admin"]}, "wrong", algorithm="HS256")
        response = await client.get("/auth/profile", headers={"Authorization": f"Bearer {forged}"})
        assert response.status_code == 401

    async def test_a_v1_token_without_a_type_claim_still_works(self, client: AsyncClient) -> None:
        """Sessions minted by NestJS survive the cutover."""
        settings = get_settings()
        v1_token = jwt.encode(
            {
                "sub": str(ADMIN_ID),
                "email": "owner@dileepa.dev",
                "roles": ["admin"],
                "exp": 2_000_000_000,
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        response = await client.get(
            "/auth/profile", headers={"Authorization": f"Bearer {v1_token}"}
        )
        assert response.status_code == 200

    async def test_refresh_rejects_a_disabled_account(
        self, client: AsyncClient, repositories: Repos, refresh_token: str
    ) -> None:
        await repositories["users"].update(str(ADMIN_ID), {"isActive": False})
        response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "account_disabled"


class TestRoles:
    async def test_profile_needs_a_token(self, client: AsyncClient) -> None:
        response = await client.get("/auth/profile")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "missing_token"

    async def test_profile_never_returns_the_password_hash(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.get("/auth/profile", headers=admin_headers)
        assert response.status_code == 200
        assert "passwordHash" not in response.text

    async def test_writes_need_the_admin_role(
        self, client: AsyncClient, editor_headers: Headers
    ) -> None:
        response = await client.post(
            "/tools",
            headers=editor_headers,
            json={"name": "x", "logo": {"light": "l", "dark": "d"}},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "insufficient_role"

    async def test_writes_are_closed_to_anonymous_callers(self, client: AsyncClient) -> None:
        response = await client.post(
            "/tools", json={"name": "x", "logo": {"light": "l", "dark": "d"}}
        )
        assert response.status_code == 401

    async def test_admin_may_write(self, client: AsyncClient, admin_headers: Headers) -> None:
        response = await client.post(
            "/tools",
            headers=admin_headers,
            json={"name": "Python", "logo": {"light": "l.svg", "dark": "d.svg"}},
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Python"

    async def test_a_bad_token_on_a_public_endpoint_is_just_anonymous(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/tools", headers={"Authorization": "Bearer nonsense"})
        assert response.status_code == 200


class TestApiKey:
    async def test_sync_requires_the_key(self, client: AsyncClient) -> None:
        response = await client.post("/blogs/sync", json={})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "missing_api_key"

    async def test_sync_rejects_a_wrong_key(self, client: AsyncClient) -> None:
        response = await client.post("/blogs/sync", headers={"x-api-key": "nope"}, json={})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_api_key"

    async def test_an_admin_jwt_does_not_open_the_sync_endpoint(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        # The pipeline's key is the only credential for this path, as in v1.
        response = await client.post("/blogs/sync", headers=admin_headers, json={})
        assert response.status_code == 401


async def test_role_check_reads_roles_from_the_token(client: AsyncClient) -> None:
    multi_role = token_for(ADMIN_ID, "owner@dileepa.dev", ["editor", "admin"])
    response = await client.post(
        "/tools",
        headers={"Authorization": f"Bearer {multi_role}"},
        json={"name": "Go", "logo": {"light": "l", "dark": "d"}},
    )
    assert response.status_code == 201
