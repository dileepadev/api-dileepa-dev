"""Configuration: which env file loads, and what production refuses to start with.

Every environment has its own complete file and exactly one is read — no merging,
no precedence order. These tests pin that, and the production checks, because the
failure mode they guard against is silent: an app that comes up announcing one
environment while holding another's database.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import (
    Settings,
    database_label,
    env_file,
    get_settings,
    selected_environment,
)

PROD_SECRET = "a-secret-long-enough-for-hs256-and-then-some"
PROD_URI = "mongodb+srv://user:pw@cluster0.example.mongodb.net/dileepa"

ProductionFactory = Callable[..., Settings]


@pytest.fixture
def production(monkeypatch: pytest.MonkeyPatch) -> ProductionFactory:
    """Builds a production-shaped Settings.

    The process environment has to move with it: `_reject_environment_mismatch`
    compares the two on purpose, so a production Settings built under
    `ENVIRONMENT=development` is a misconfiguration by definition — which is
    what `TestEnvironmentMismatch` covers separately.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    def build(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "ENVIRONMENT": "production",
            "MONGODB_URI": PROD_URI,
            "JWT_SECRET": PROD_SECRET,
            "BLOG_SYNC_API_KEY": "a-real-key",
            "RESEND_API_KEY": "re_real",
            "CLOUDINARY_API_SECRET": "real-secret",
            "CORS_ORIGINS": "https://dileepa.dev",
        }
        values.update(overrides)
        return Settings(**values)

    return build


class TestEnvFileSelection:
    def test_defaults_to_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("DOTENV_DISABLED", raising=False)
        assert selected_environment() == "development"
        assert env_file() == Path(".env.development")

    @pytest.mark.parametrize("environment", ["development", "staging", "production"])
    def test_environment_names_the_file(
        self, monkeypatch: pytest.MonkeyPatch, environment: str
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", environment)
        monkeypatch.delenv("DOTENV_DISABLED", raising=False)
        assert env_file() == Path(f".env.{environment}")

    def test_only_one_file_is_ever_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The whole point of the layout. `env_file` returns a single path, not a
        # sequence, so there is no second file to override the first and no
        # precedence order for anyone to have to remember.
        monkeypatch.delenv("DOTENV_DISABLED", raising=False)
        assert isinstance(env_file(), Path)

    def test_the_plain_dotenv_file_is_not_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # `.env` has no environment in its name, so nothing loads it. A leftover
        # one from the old layout must not quietly come back into effect.
        monkeypatch.delenv("DOTENV_DISABLED", raising=False)
        for environment in ("development", "staging", "production"):
            monkeypatch.setenv("ENVIRONMENT", environment)
            assert env_file() != Path(".env")

    def test_environment_is_case_and_space_insensitive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "  Production ")
        assert selected_environment() == "production"

    def test_blank_environment_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "   ")
        assert selected_environment() == "development"

    def test_dotenv_can_be_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # What keeps the offline suite offline on a developer's own machine.
        monkeypatch.setenv("DOTENV_DISABLED", "1")
        assert env_file() is None


class TestFileIsActuallyLoaded:
    """The selected file has to be read, and nothing beside it."""

    def test_values_come_from_the_named_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / ".env.production").write_text(
            "ENVIRONMENT=production\nMONGODB_DB=from-production\n"
        )
        (tmp_path / ".env.development").write_text(
            "ENVIRONMENT=development\nMONGODB_DB=from-development\n"
        )
        # A leftover .env from the old layout, which must be ignored entirely.
        (tmp_path / ".env").write_text("MONGODB_DB=from-plain-dotenv\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DOTENV_DISABLED", raising=False)
        monkeypatch.delenv("MONGODB_DB", raising=False)

        monkeypatch.setenv("ENVIRONMENT", "production")
        assert Settings().mongodb_db == "from-production"

        monkeypatch.setenv("ENVIRONMENT", "development")
        assert Settings().mongodb_db == "from-development"

    def test_the_process_environment_still_wins(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / ".env.development").write_text(
            "ENVIRONMENT=development\nMONGODB_DB=from-file\n"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DOTENV_DISABLED", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("MONGODB_DB", "from-the-shell")
        assert Settings().mongodb_db == "from-the-shell"

    def test_a_missing_file_is_not_an_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Every deployment takes this path: the values arrive as real
        # environment variables and no file exists at all.
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DOTENV_DISABLED", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert Settings().environment == "development"


class TestEnvironmentMismatch:
    def test_rejects_configuration_from_the_wrong_cascade(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "development")
        with pytest.raises(ValidationError, match="in the process environment but"):
            Settings(ENVIRONMENT="production")

    def test_the_error_names_the_file_it_loaded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # The point of the message is telling the operator which file ran. Run
        # it from an empty directory: dotenv paths resolve against the working
        # directory, and reading the developer's own file here would make the
        # test depend on whatever happens to be in it.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("DOTENV_DISABLED", raising=False)
        with pytest.raises(ValidationError, match=r"\.env\.development is the wrong file"):
            Settings(ENVIRONMENT="production")

    def test_accepts_a_matching_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "staging")
        assert Settings(ENVIRONMENT="staging").environment == "staging"


class TestProductionProblems:
    def test_a_well_formed_production_config_has_none(self, production: ProductionFactory) -> None:
        assert production().production_problems() == []

    def test_placeholder_jwt_secret_is_refused(self, production: ProductionFactory) -> None:
        problems = production(JWT_SECRET="change_me").production_problems()
        assert any("JWT_SECRET" in p for p in problems)

    def test_the_field_default_is_treated_as_a_placeholder(
        self, production: ProductionFactory
    ) -> None:
        # `defaultSecret` is the field default, so an unset JWT_SECRET in
        # production has to fail exactly like an obvious placeholder does.
        problems = production(JWT_SECRET="defaultSecret").production_problems()
        assert any("JWT_SECRET" in p for p in problems)

    @pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
    def test_local_database_is_refused(self, production: ProductionFactory, host: str) -> None:
        problems = production(MONGODB_URI=f"mongodb://{host}:27017/dileepa").production_problems()
        assert any("local database" in p for p in problems)

    def test_wildcard_cors_is_refused(self, production: ProductionFactory) -> None:
        problems = production(CORS_ORIGINS="*").production_problems()
        assert any("CORS_ORIGINS" in p for p in problems)

    def test_a_copy_source_is_refused(self, production: ProductionFactory) -> None:
        """Production does not serve the maintenance routes, so nothing reads these.

        A value present therefore means production booted with another
        environment's file, and the next question is which of the other values
        came from it too — so this stops the boot rather than being ignored.
        """
        problems = production(SOURCE_MONGODB_URI=PROD_URI).production_problems()
        assert any("SOURCE_MONGODB_URI" in problem for problem in problems)

    def test_a_copy_source_database_alone_is_refused(self, production: ProductionFactory) -> None:
        problems = production(SOURCE_MONGODB_DB="production").production_problems()
        assert any("SOURCE_MONGODB_URI" in problem for problem in problems)

    def test_missing_blog_sync_key_is_refused(self, production: ProductionFactory) -> None:
        problems = production(BLOG_SYNC_API_KEY="").production_problems()
        assert any("BLOG_SYNC_API_KEY" in p for p in problems)


class TestProductionWarnings:
    def test_short_secret_warns_but_does_not_block(self, production: ProductionFactory) -> None:
        # It has to keep matching whatever signed the tokens already sitting in
        # the owner's browser, so refusing to boot over its length would force a
        # re-login at the worst possible moment. The NestJS deployment is gone,
        # but the sessions it minted are not.
        settings = production(JWT_SECRET="short-but-real")
        assert settings.production_problems() == []
        assert any("at least 32" in w for w in settings.production_warnings())

    def test_missing_integration_keys_warn(self, production: ProductionFactory) -> None:
        warnings = production(RESEND_API_KEY="", CLOUDINARY_API_SECRET="").production_warnings()
        assert any("RESEND_API_KEY" in w for w in warnings)
        assert any("CLOUDINARY_API_SECRET" in w for w in warnings)

    def test_docs_enabled_in_production_warns(self, production: ProductionFactory) -> None:
        warnings = production(DOCS_ENABLED=True).production_warnings()
        assert any("DOCS_ENABLED" in w for w in warnings)


class TestDatabaseLabel:
    def test_strips_credentials(self) -> None:
        # This string gets printed by the operations scripts before they write.
        label = database_label("mongodb+srv://admin:hunter2@cluster0.example.net/dileepa")
        assert label == "cluster0.example.net/dileepa"
        assert "hunter2" not in label
        assert "admin" not in label

    def test_explicit_database_wins_over_the_uri_path(self) -> None:
        assert database_label("mongodb://host:27017/ignored", "chosen") == "host/chosen"

    def test_uri_without_a_database_is_labelled_default(self) -> None:
        assert database_label("mongodb://host:27017") == "host/default"

    def test_settings_expose_their_own_target(self) -> None:
        assert get_settings().database_label.endswith("/test")


class TestDevelopmentIsUnaffected:
    """None of the production checks may fire outside production.

    A developer's localhost URI and placeholder secret are the correct values
    there, and a guard that nags about them is a guard people learn to ignore.
    """

    def test_no_problems(self) -> None:
        assert Settings(JWT_SECRET="change_me").production_problems() == []

    def test_no_warnings(self) -> None:
        assert Settings().production_warnings() == []
