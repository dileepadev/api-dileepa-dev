"""The development-only database maintenance routes.

These two routes empty the database the API is pointed at, so what is worth
pinning is not that they work — it is everything that stops them working. The
guards are layered deliberately (see `app/routers/maintenance.py`), and each
layer is tested on its own here, because a layer that silently stopped
working would be invisible while the ones above it still held.

The copy itself is not exercised: it talks to two real databases, and this
suite stays offline. Every guard runs before either connection is opened,
which is what makes them testable here and is also why they are in that order.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.routes import flatten_routes
from app.main import create_app
from app.routers.maintenance import (
    COPIED_COLLECTIONS,
    EXCLUDED_COLLECTIONS,
    _confirmation_phrase,
)

from .types import Headers

CONFIRM = "dev"


@pytest.fixture
def production_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    yield create_app()
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()


@pytest.fixture
async def production_client(production_app: Any) -> Any:
    transport = ASGITransport(app=production_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


class TestNotInProduction:
    """Guard 1: the routes do not exist on the production API."""

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/maintenance/database"),
            ("POST", "/maintenance/database/copy"),
            ("POST", "/maintenance/database/clear"),
        ],
    )
    async def test_route_is_not_registered(
        self, production_client: AsyncClient, admin_headers: Headers, method: str, path: str
    ) -> None:
        """404, not 403.

        A 403 would mean the route exists and declined. These are not
        registered at all, so there is nothing on the production API to reach
        even with a valid admin token — which is a stronger statement than any
        check inside a handler can make.
        """
        response = await production_client.request(method, path, headers=admin_headers, json={})
        assert response.status_code == 404

    async def test_the_routes_do_exist_in_development(self, app: Any) -> None:
        """The counterpart to the test above: absent there, present here.

        `flatten_routes` rather than `app.routes`, because FastAPI 0.141 keeps
        an included router nested instead of flattening its routes into the
        app — the same thing that made the rate limiter miss every endpoint.
        """
        paths = {route.path for route in flatten_routes(app.routes) if hasattr(route, "path")}
        assert "/maintenance/database/copy" in paths
        assert "/maintenance/database/clear" in paths


class TestAuthorisation:
    """Guard: admin, not merely a valid token."""

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/maintenance/database"),
            ("POST", "/maintenance/database/copy"),
            ("POST", "/maintenance/database/clear"),
        ],
    )
    async def test_anonymous_is_rejected(self, client: AsyncClient, method: str, path: str) -> None:
        response = await client.request(method, path, json={"confirm": CONFIRM})
        assert response.status_code == 401

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/maintenance/database"),
            ("POST", "/maintenance/database/copy"),
            ("POST", "/maintenance/database/clear"),
        ],
    )
    async def test_a_non_admin_token_is_rejected(
        self, client: AsyncClient, editor_headers: Headers, method: str, path: str
    ) -> None:
        response = await client.request(
            method, path, headers=editor_headers, json={"confirm": CONFIRM}
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "insufficient_role"


class TestConfirmation:
    """Guard 5: the caller names the database they are emptying."""

    async def test_clear_rejects_a_wrong_confirmation(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post(
            "/maintenance/database/clear",
            headers=admin_headers,
            json={"confirm": "production"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "confirmation_mismatch"

    async def test_clear_rejects_an_empty_confirmation(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post(
            "/maintenance/database/clear", headers=admin_headers, json={"confirm": ""}
        )
        assert response.status_code == 400

    async def test_the_phrase_is_the_target_database_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DOTENV_DISABLED", "1")
        settings = Settings(MONGODB_URI="mongodb://localhost:27017/x", MONGODB_DB="dev")
        assert _confirmation_phrase(settings) == "dev"


class TestSourceGuards:
    """Guards 3 and 4, both checked before the copy opens anything."""

    async def test_copy_without_a_source_is_unavailable(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        """The offline suite configures no source, which is the unset case."""
        response = await client.post(
            "/maintenance/database/copy",
            headers=admin_headers,
            json={"confirm": CONFIRM},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "copy_source_not_configured"

    def test_a_source_equal_to_the_target_is_detected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Compared on the credential-free label, not the raw URI.

        Two spellings of one database — a different user, an extra query
        parameter — must not present themselves as two databases, because a
        copy onto itself empties the collection it is reading from.
        """
        monkeypatch.setenv("DOTENV_DISABLED", "1")
        settings = Settings(
            MONGODB_URI="mongodb+srv://alice:pw@cluster0.example.net/dileepa",
            MONGODB_DB="dev",
            SOURCE_MONGODB_URI="mongodb+srv://bob:other@cluster0.example.net/dileepa?retryWrites=true",
            SOURCE_MONGODB_DB="dev",
        )
        assert settings.source_is_target is True

    def test_a_genuinely_different_source_is_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DOTENV_DISABLED", "1")
        settings = Settings(
            MONGODB_URI="mongodb+srv://alice:pw@cluster0.example.net/dileepa",
            MONGODB_DB="dev",
            SOURCE_MONGODB_URI="mongodb+srv://alice:pw@cluster0.example.net/dileepa",
            SOURCE_MONGODB_DB="production",
        )
        assert settings.source_is_target is False
        assert settings.copy_source_configured is True

    def test_the_label_never_carries_the_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """This value is rendered in a browser and returned by the API."""
        monkeypatch.setenv("DOTENV_DISABLED", "1")
        settings = Settings(
            MONGODB_URI="mongodb://localhost:27017/x",
            SOURCE_MONGODB_URI="mongodb+srv://reader:sup3rsecret@cluster0.example.net/dileepa",
            SOURCE_MONGODB_DB="production",
        )
        label = settings.source_database_label or ""
        assert "sup3rsecret" not in label
        assert "reader" not in label
        assert label == "cluster0.example.net/production"


class TestScope:
    async def test_users_is_never_copied(self) -> None:
        """The account you are signed in as is not replaced mid-session.

        `users` holds the password hash the admin authenticates with. Copying
        production's over development's would change the credentials of the
        environment the person is standing in, while they are standing in it.
        """
        assert "users" in EXCLUDED_COLLECTIONS
        assert "users" not in COPIED_COLLECTIONS

    async def test_every_other_collection_is_copied(self) -> None:
        from app.core.db import COLLECTIONS

        assert set(COPIED_COLLECTIONS) == set(COLLECTIONS) - EXCLUDED_COLLECTIONS
