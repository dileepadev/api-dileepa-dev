"""The generated spec is the contract both frontends build against.

`dileepa-dev` generates `lib/api-types.ts` from it and `admin-dileepa-dev`
generates a typed client, so a shape that regresses here breaks two repositories
at once.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.main import create_app

Spec = dict[str, Any]

RESOURCES = ["experiences", "educations", "tools", "communities", "videos"]


@pytest.fixture(scope="module")
def spec() -> Spec:
    return create_app().openapi()


def test_version_endpoint_reports_the_package_version() -> None:
    from app.routers.meta import app_version

    assert app_version() == "2.0.0"


def test_metadata(spec: Spec) -> None:
    assert spec["info"]["title"] == "api.dileepa.dev"
    # Pinned so a release that forgets to bump pyproject.toml fails here.
    assert spec["info"]["version"] == "2.0.0"
    assert spec["info"]["license"]["name"] == "MIT"


@pytest.mark.parametrize("resource", RESOURCES)
def test_every_factory_built_resource_has_the_same_operations(spec: Spec, resource: str) -> None:
    """The factory exists so these five cannot drift apart."""
    assert set(spec["paths"][f"/{resource}"]) == {"get", "post"}
    assert set(spec["paths"][f"/{resource}/{{identifier}}"]) == {"get", "patch", "delete"}
    assert set(spec["paths"][f"/{resource}/order"]) == {"patch"}


@pytest.mark.parametrize("resource", RESOURCES)
def test_request_and_response_models_are_named_not_inlined(spec: Spec, resource: str) -> None:
    singular = {
        "experiences": "Experience",
        "educations": "Education",
        "tools": "Tool",
        "communities": "Community",
        "videos": "Video",
    }[resource]
    post = spec["paths"][f"/{resource}"]["post"]
    body = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert body.endswith(f"/{singular}Create")
    response = post["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    assert response.endswith(f"/{singular}")


@pytest.mark.parametrize("resource", RESOURCES)
def test_lists_use_the_page_envelope(spec: Spec, resource: str) -> None:
    singular = {
        "experiences": "Experience",
        "educations": "Education",
        "tools": "Tool",
        "communities": "Community",
        "videos": "Video",
    }[resource]
    schema = spec["paths"][f"/{resource}"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    assert schema.endswith(f"/Page_{singular}_")


def test_page_envelope_shape(spec: Spec) -> None:
    page = spec["components"]["schemas"]["Page_Tool_"]
    assert set(page["properties"]) == {"items", "total", "limit", "offset"}


def test_every_endpoint_is_documented(spec: Spec) -> None:
    undocumented = [
        f"{method.upper()} {path}"
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if not operation.get("summary")
    ]
    assert undocumented == []


def test_every_endpoint_is_tagged(spec: Spec) -> None:
    untagged = [
        f"{method.upper()} {path}"
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if not operation.get("tags")
    ]
    assert untagged == []


def test_deprecated_paths_are_marked(spec: Spec) -> None:
    assert spec["paths"]["/events"]["get"]["deprecated"] is True
    assert spec["paths"]["/auth/sign-in"]["post"]["deprecated"] is True
    assert spec["paths"]["/upload"]["post"]["deprecated"] is True


def test_the_new_resources_are_present(spec: Spec) -> None:
    for path in ("/projects", "/projects/{identifier}", "/sessions", "/sessions/{identifier}"):
        assert path in spec["paths"]


def test_health_and_version_are_public(spec: Spec) -> None:
    for path in ("/health", "/version"):
        assert "security" not in spec["paths"][path]["get"]


def test_camel_case_on_the_wire(spec: Spec) -> None:
    """Python is snake_case; the API is camelCase. One alias generator, no drift."""
    blog = spec["components"]["schemas"]["BlogPost"]["properties"]
    assert "publishedDate" in blog
    assert "readingTimeMinutes" in blog
    assert "published_date" not in blog


def test_token_response_keeps_v1_field_names(spec: Spec) -> None:
    """`access_token`, not `accessToken`: the admin app reads that name today."""
    token = spec["components"]["schemas"]["TokenPair"]["properties"]
    assert set(token) == {"access_token", "refresh_token", "token_type", "expires_in"}


def test_docs_are_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        app = create_app()
        assert app.docs_url is None
        assert app.redoc_url is None
        assert app.openapi_url is None
    finally:
        monkeypatch.setenv("ENVIRONMENT", "development")
        get_settings.cache_clear()
