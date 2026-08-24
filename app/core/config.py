"""Application configuration, read once from the environment.

Every value the app needs is declared here. Nothing else in the codebase reads
`os.environ` directly, so the full set of required configuration is visible in
one file and `.env.example` can be checked against it.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]

# Local development origins, always allowed outside production. The ports are
# the main site, the admin app, and the links app running side by side.
_LOCAL_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:4321",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    environment: Environment = Field(default="development", alias="ENVIRONMENT")
    port: int = Field(default=8000, alias="PORT")
    site_url: str = Field(default="https://dileepa.dev", alias="SITE_URL")

    # Comma-separated, not JSON: this value is edited by hand through
    # `fastapi cloud env set`, and JSON quoting there is a foot-gun.
    cors_origins_raw: str = Field(default="", alias="CORS_ORIGINS")

    # MongoDB — the same cluster and collections the NestJS app uses.
    mongodb_uri: str = Field(default="mongodb://localhost:27017/dileepa", alias="MONGODB_URI")
    mongodb_db: str | None = Field(default=None, alias="MONGODB_DB")

    # Auth. Algorithm, secret and access-token lifetime match the NestJS
    # implementation so tokens minted before the cutover stay valid.
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
        # concern mode". Carried over from src/app.module.ts.
        return value.replace("majority/?authMechanism", "majority&authMechanism")

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
        # Vercel preview deployments get a fresh hostname per build, so they
        # cannot be enumerated in an allowlist. Never widen this to `.*`.
        return r"https://[a-z0-9-]+-dileepadev-projects\.vercel\.app"


@lru_cache
def get_settings() -> Settings:
    return Settings()
