"""Application configuration, read once from the environment.

Every value the app needs is declared here. Nothing else in the codebase reads
`os.environ` directly, so the full set of required configuration is visible in
one file and the `.env.*.example` templates can be checked against it.

**Every environment has its own file, and only one of them is ever read.**
`ENVIRONMENT` names it:

    ENVIRONMENT=development  ->  .env.development
    ENVIRONMENT=production   ->  .env.production
    ENVIRONMENT=staging      ->  .env.staging

Nothing merges. Each file is complete on its own, so the value in front of you
is the value in effect — there is no second file quietly overriding it, and no
order to remember. Shared values are duplicated across the files on purpose:
that duplication is the cost of never having to ask which file won.

Real environment variables still beat the file. That is how production works:
FastAPI Cloud sets them with `fastapi cloud env set` and no dotenv file exists
on the deployment at all, so these files are a local-development convenience.

`ENVIRONMENT` is read from the process environment to choose the file, which
makes it the one value that cannot live *only* in a dotenv file. Exporting one
environment and writing another into the file is a misconfiguration serious
enough to load the wrong cluster's credentials, so
`_reject_environment_mismatch` refuses to start instead of guessing.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]

DEFAULT_ENVIRONMENT = "development"

# Local development origins, always allowed outside production. The ports are
# the main site, the admin app, and the links app running side by side.
_LOCAL_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:4321",
)

# The values the example templates ship. Production must never boot with one,
# which is the difference between "the deploy is misconfigured" and "anyone
# can mint an admin token".
_PLACEHOLDER_SECRETS = frozenset(
    {"", "change_me", "changeme", "defaultSecret", "your_jwt_secret", "secret"}
)

# Hosts that mean "someone deployed their laptop's configuration". These are
# matched against, never bound to, so S104's bind-all warning does not apply.
_LOCAL_DB_HOSTS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",  # noqa: S104
    "host.docker.internal",
)


def database_label(uri: str, database: str | None = None) -> str:
    """Host and database name, with any credentials stripped. Safe to print.

    The operations scripts show this before they touch anything, so it has to be
    readable by a human deciding whether to type the name back — and it must
    never carry the password sitting in the same URI. It takes the URI as an
    argument rather than reading settings because those scripts accept `--uri`,
    and the value that matters is the one they will actually connect with.
    """
    parts = urlsplit(uri)
    host = parts.hostname or "unknown-host"
    name = database or (parts.path.lstrip("/").split("?")[0] or "default")
    return f"{host}/{name}"


def selected_environment() -> str:
    """Which environment's dotenv file loads.

    Read from the process environment only — see the module docstring for why it
    cannot be read from the files it is choosing between.
    """
    value = os.environ.get("ENVIRONMENT", DEFAULT_ENVIRONMENT).strip().lower()
    return value or DEFAULT_ENVIRONMENT


def env_file() -> Path | None:
    """The single dotenv file this environment reads, or None if it reads none.

    A missing file is ignored by pydantic-settings rather than raised, which is
    what lets a deployment — where the values arrive as real environment
    variables and no file exists — take the same path as a laptop.

    `DOTENV_DISABLED=1` opts out entirely. The test suite sets it so a developer
    who happens to have a populated `.env.development` cannot leak real
    credentials into an offline suite; `AGENTS.md` requires that suite to stay
    offline, and this is what makes it true rather than merely intended.
    """
    if os.environ.get("DOTENV_DISABLED") == "1":
        return None
    return Path(f".env.{selected_environment()}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    def __init__(self, **values: Any) -> None:
        # The file is resolved here rather than in `model_config`, which is
        # evaluated once when this class is defined. That distinction is not
        # academic: it would bake in whatever `ENVIRONMENT` happened to be at
        # import time, so anything importing this module before the environment
        # was set would silently read the wrong file for the life of the
        # process — and a test could never change it.
        values.setdefault("_env_file", env_file())
        super().__init__(**values)

    # Application
    environment: Environment = Field(default="development", alias="ENVIRONMENT")
    port: int = Field(default=8000, alias="PORT")
    site_url: str = Field(default="https://dileepa.dev", alias="SITE_URL")

    # Comma-separated, not JSON: this value is edited by hand through
    # `fastapi cloud env set`, and JSON quoting there is a foot-gun.
    cors_origins_raw: str = Field(default="", alias="CORS_ORIGINS")

    # MongoDB — the same cluster and collections v1 used. Nothing re-seeds.
    mongodb_uri: str = Field(default="mongodb://localhost:27017/dileepa", alias="MONGODB_URI")
    mongodb_db: str | None = Field(default=None, alias="MONGODB_DB")

    # Auth. Algorithm, secret and access-token lifetime match what v1 used, so
    # a token it minted — which lives in a browser, not in a deployment — is
    # still valid here.
    jwt_secret: str = Field(default="defaultSecret", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # Cloudinary is the only image backend. Azure Blob Storage is retired.
    cloudinary_cloud_name: str = Field(default="", alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: str = Field(default="", alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str = Field(default="", alias="CLOUDINARY_API_SECRET")
    cloudinary_root_folder: str = Field(default="api-dileepa-dev", alias="CLOUDINARY_ROOT_FOLDER")

    # Contact form
    resend_api_key: str = Field(default="", alias="RESEND_API_KEY")
    resend_from_email: str = Field(default="onboarding@resend.dev", alias="RESEND_FROM_EMAIL")
    contact_email: str = Field(default="contact@dileepa.dev", alias="CONTACT_EMAIL")

    # Machine-to-machine key for the blog pipeline
    blog_sync_api_key: str = Field(default="", alias="BLOG_SYNC_API_KEY")

    # Rate limits, in slowapi's notation
    rate_limit_default: str = Field(default="60/minute", alias="RATE_LIMIT_DEFAULT")
    rate_limit_contact: str = Field(default="3/minute", alias="RATE_LIMIT_CONTACT")
    # Comments post without review, so this is the main thing standing between
    # the blog and a spam run. Looser than contact — a reader may legitimately
    # reply twice in a conversation — and far tighter than the default.
    rate_limit_comment: str = Field(default="6/minute", alias="RATE_LIMIT_COMMENT")

    # Interactive docs stay off in production. This is the v1 posture, kept.
    docs_enabled: bool | None = Field(default=None, alias="DOCS_ENABLED")

    # Scalar renders the API reference from its CDN. Pinning a version here
    # rather than tracking latest means the docs page cannot change under us.
    scalar_js_url: str = Field(
        default="https://cdn.jsdelivr.net/npm/@scalar/api-reference",
        alias="SCALAR_JS_URL",
    )

    @field_validator("mongodb_uri")
    @classmethod
    def _fix_write_concern_separator(cls, value: str) -> str:
        # The stored connection string has `majority/?authMechanism`, which the
        # driver reads as a stray path segment and then fails with "No write
        # concern mode". The v1 application applied the same fix; the malformed
        # value is in the stored configuration, not in either codebase.
        return value.replace("majority/?authMechanism", "majority&authMechanism")

    @model_validator(mode="after")
    def _reject_environment_mismatch(self) -> Settings:
        """Refuse to run as one environment while configured as another.

        Without this the selection fails quietly and in the worst direction:
        nothing is exported, so `.env.development` loads — and then it says
        `ENVIRONMENT=production`, and the app announces itself as production
        while holding development's database and secret.
        """
        selected = selected_environment()
        if self.environment == selected:
            return self

        loaded = env_file()
        source = f"{loaded} is the wrong file" if loaded else "no dotenv file was loaded"
        raise ValueError(
            f"ENVIRONMENT is {selected!r} in the process environment but {self.environment!r} "
            f"in the loaded configuration, so {source}. "
            f"Export ENVIRONMENT={self.environment} instead of setting it in a dotenv file."
        )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def serve_docs(self) -> bool:
        if self.docs_enabled is not None:
            return self.docs_enabled
        return not self.is_production

    @property
    def docs_path(self) -> str:
        """Where the API reference is served. Scalar renders it, not Swagger UI."""
        return "/docs"

    @property
    def openapi_url(self) -> str | None:
        return "/api-json" if self.serve_docs else None

    @property
    def scalar_cdn_origin(self) -> str:
        """The origin the docs page's Content-Security-Policy has to allow."""
        parts = urlsplit(self.scalar_js_url)
        return f"{parts.scheme}://{parts.netloc}" if parts.netloc else ""

    @property
    def cors_origins(self) -> list[str]:
        configured = [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]
        if self.is_production:
            return configured or ["https://dileepa.dev", "https://www.dileepa.dev"]
        return [*_LOCAL_ORIGINS, *configured]

    @property
    def cors_origin_regex(self) -> str:
        # This is for the **front ends**, which are still on Vercel:
        # `dileepa-dev` and `admin-dileepa-dev` get a fresh preview hostname per
        # build, so they cannot be enumerated in an allowlist. It has nothing to
        # do with the API's own retired Vercel deployment -- that is gone, and
        # this pattern is still needed. Never widen it to `.*`.
        return r"https://[a-z0-9-]+-dileepadev-projects\.vercel\.app"

    @property
    def database_label(self) -> str:
        """Where this process is pointed, with credentials stripped."""
        return database_label(self.mongodb_uri, self.mongodb_db)

    def production_problems(self) -> list[str]:
        """Configuration that must not reach production. Empty means safe.

        Checked at startup rather than in a validator so that constructing a
        production-shaped `Settings` stays possible in a test. Only genuinely
        unsafe values are listed here — see `production_warnings` for the rest.
        """
        if not self.is_production:
            return []

        problems: list[str] = []

        if self.jwt_secret.strip() in _PLACEHOLDER_SECRETS:
            problems.append("JWT_SECRET is still a placeholder — every token would be forgeable.")

        host = (urlsplit(self.mongodb_uri).hostname or "").lower()
        if host in _LOCAL_DB_HOSTS:
            problems.append(
                f"MONGODB_URI points at {host!r}, which is a local database, not the cluster."
            )

        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS contains '*'. The allowlist must name real origins.")

        if not self.blog_sync_api_key.strip():
            problems.append("BLOG_SYNC_API_KEY is empty, so POST /blogs/sync cannot authenticate.")

        return problems

    def production_warnings(self) -> list[str]:
        """Worth saying out loud, but not worth refusing to start over.

        `JWT_SECRET` length is deliberately a warning: it still has to verify
        the tokens v1 minted, which live in browsers rather than in any
        deployment, and failing the boot over a short-but-correct secret would
        take production down to fix a weakness that predates this service.
        """
        if not self.is_production:
            return []

        warnings: list[str] = []

        if len(self.jwt_secret) < 32:
            warnings.append(
                f"JWT_SECRET is {len(self.jwt_secret)} characters; HS256 wants at least 32. "
                "Rotate it once no v1-issued token can still be in a browser — "
                "REFRESH_TOKEN_EXPIRE_DAYS after the cutover."
            )
        if not self.resend_api_key.strip():
            warnings.append("RESEND_API_KEY is empty — the contact form will return 503.")
        if not self.cloudinary_api_secret.strip():
            warnings.append("CLOUDINARY_API_SECRET is empty — image uploads will return 503.")
        if self.serve_docs:
            warnings.append(
                "DOCS_ENABLED is true in production, so /docs and /api-json are public."
            )

        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
