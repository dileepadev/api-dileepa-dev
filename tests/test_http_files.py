"""The request files in `http/` have to keep up with the routes.

`README.md`'s endpoint table drifts because nothing checks it. These files would
drift the same way, and a request file that silently stops covering an endpoint
is worse than no file at all — it reads like coverage.

So: every route in the OpenAPI document needs a request in `http/`. The check
runs one way only. A request that matches no route is allowed on purpose, since
some of them exist to pin a failure — `POST /events` is there to stay a 405.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.main import create_app

HTTP_DIR = Path(__file__).resolve().parent.parent / "http"

# Only lines addressed through the environment's base URL are requests. It also
# keeps a stray "POST ..." inside a multipart body from being read as one.
REQUEST_LINE = re.compile(
    r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\{\{baseUrl\}\}(\S*)",
    re.MULTILINE,
)


def http_files() -> list[Path]:
    return sorted(HTTP_DIR.glob("*.http"))


def requests_in(path: Path) -> list[tuple[str, str]]:
    """(method, path) for every request in one file, query strings dropped."""
    found = []
    for method, raw in REQUEST_LINE.findall(path.read_text(encoding="utf-8")):
        route = raw.split("?", 1)[0].split("#", 1)[0]
        found.append((method, route or "/"))
    return found


def documented_routes() -> set[tuple[str, str]]:
    spec = create_app().openapi()
    return {
        (method.upper(), route)
        for route, operations in spec["paths"].items()
        for method in operations
        if method.upper() != "HEAD"
    }


def matches(template: str, actual: str) -> bool:
    """Does `actual` fit the OpenAPI `template`?

    Template segments in braces are placeholders and match anything, which is
    what makes `/events/{{slug}}` in a file line up with
    `/events/{identifier}` in the spec. A trailing placeholder is allowed to
    swallow the rest of the path, because `/uploads/{public_id:path}` is
    declared as a path converter — Cloudinary public ids contain slashes.
    """
    want = [s for s in template.split("/") if s]
    got = [s for s in actual.split("/") if s]

    if len(want) != len(got):
        trailing_is_placeholder = bool(want) and want[-1].startswith("{")
        if not (trailing_is_placeholder and len(got) > len(want)):
            return False
        got = [*got[: len(want) - 1], "/".join(got[len(want) - 1 :])]

    return all(w.startswith("{") or w == g for w, g in zip(want, got, strict=True))


def covered() -> set[tuple[str, str]]:
    """Every documented route that some request file exercises."""
    requests = [(m, p) for f in http_files() for m, p in requests_in(f)]
    hits = set()
    for method, template in documented_routes():
        for actual_method, actual in requests:
            if actual_method == method and matches(template, actual):
                hits.add((method, template))
                break
    return hits


class TestRequestFilesExist:
    def test_there_is_one_per_router_module(self) -> None:
        # The mapping is deliberate: http/<name>.http tracks app/routers/<name>.py,
        # so "where do I add this request" never needs a decision. `crud.py` is
        # the factory the five profile resources are built from, not a router.
        routers = {
            p.stem
            for p in (HTTP_DIR.parent / "app" / "routers").glob("*.py")
            if p.stem not in {"__init__", "crud"}
        }
        assert {p.stem for p in http_files()} == routers

    def test_every_file_has_requests(self) -> None:
        empty = [f.name for f in http_files() if not requests_in(f)]
        assert not empty, f"No requests found in: {', '.join(empty)}"

    def test_the_upload_fixture_is_present(self) -> None:
        # uploads.http streams this with `< ./fixtures/example.png`; without it
        # every upload request fails on something unrelated to the endpoint.
        fixture = HTTP_DIR / "fixtures" / "example.png"
        assert fixture.is_file()
        assert fixture.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


class TestCoverage:
    def test_every_route_has_a_request(self) -> None:
        missing = sorted(documented_routes() - covered())
        assert not missing, "No request in http/ for:\n" + "\n".join(
            f"  {method} {route}" for method, route in missing
        )

    @pytest.mark.parametrize(
        ("template", "actual", "expected"),
        [
            ("/events/{identifier}", "/events/{{slug}}", True),
            ("/events/order", "/events/order", True),
            # A literal path must not be satisfied by the placeholder route.
            ("/events/order", "/events/{{slug}}", False),
            ("/events/{identifier}", "/events", False),
            # The path converter swallows the slashes in a Cloudinary id.
            ("/uploads/{public_id}", "/uploads/nothing/here", True),
            ("/about", "/about", True),
            ("/", "/", True),
        ],
    )
    def test_matching_rules(self, template: str, actual: str, expected: bool) -> None:
        assert matches(template, actual) is expected
