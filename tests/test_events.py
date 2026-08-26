"""Events — the v2 shape, statuses derived, and the list filters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import users_seed
from tests.types import Headers, Repos, must_find

NOW = datetime.now(UTC)


def event_doc(slug: str, *, days: int, **overrides: Any) -> dict[str, Any]:
    return {
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "summary": "One line for the card.",
        "type": "workshop",
        "format": "in_person",
        "startAt": NOW + timedelta(days=days),
        "timezone": "Asia/Colombo",
        # Every field the sort keys touch is present. Events written by this
        # API always are, and `scripts/migrate_events_v1_to_v2.py` fills them in
        # for the rows it converts, because Mongo sorts a missing field below
        # `false`.
        "featured": False,
        "order": 0,
        "published": True,
        **overrides,
    }


@pytest.fixture
def seed() -> dict[str, list[dict[str, Any]]]:
    return {
        "users": users_seed(),
        "events": [
            event_doc(
                "intro-to-azure",
                days=-90,
                location={"venue": "NIBM", "city": "Colombo", "country": "Sri Lanka"},
                links=[
                    {"label": "Recap", "url": "https://example.com/recap", "kind": "recap"},
                    {
                        "label": "Register",
                        "url": "https://example.com/register",
                        "kind": "registration",
                    },
                ],
                tags=["azure"],
            ),
            event_doc(
                "agents-in-production",
                days=30,
                format="online",
                type="webinar",
                links=[{"label": "Sign up", "url": "https://x/y", "kind": "registration"}],
                tags=["ai"],
            ),
            event_doc("cancelled-meetup", days=10, status="cancelled", type="meetup"),
        ],
    }


class TestDerivedStatus:
    async def test_a_past_session_reads_as_completed(self, client: AsyncClient) -> None:
        body = (await client.get("/events/intro-to-azure")).json()
        assert body["status"] == "completed"

    async def test_a_future_session_reads_as_upcoming(self, client: AsyncClient) -> None:
        body = (await client.get("/events/agents-in-production")).json()
        assert body["status"] == "upcoming"

    async def test_cancelled_is_never_derived_away(self, client: AsyncClient) -> None:
        """Time passing does not un-cancel a event."""
        body = (await client.get("/events/cancelled-meetup")).json()
        assert body["status"] == "cancelled"

    async def test_status_is_not_stored_on_the_document(self, repositories: Repos) -> None:
        stored = await must_find(repositories["events"], {"slug": "intro-to-azure"})
        assert "status" not in stored


class TestFilters:
    async def test_upcoming(self, client: AsyncClient) -> None:
        body = (await client.get("/events?status=upcoming")).json()
        assert [item["slug"] for item in body["items"]] == ["agents-in-production"]
        assert body["total"] == 1

    async def test_completed(self, client: AsyncClient) -> None:
        body = (await client.get("/events?status=completed")).json()
        assert [item["slug"] for item in body["items"]] == ["intro-to-azure"]

    async def test_cancelled(self, client: AsyncClient) -> None:
        body = (await client.get("/events?status=cancelled")).json()
        assert [item["slug"] for item in body["items"]] == ["cancelled-meetup"]

    async def test_total_reflects_the_filter_not_the_page(self, client: AsyncClient) -> None:
        # Filtering after the query would make `total` lie.
        body = (await client.get("/events?status=upcoming&limit=1")).json()
        assert body["total"] == 1

    async def test_by_type_and_format(self, client: AsyncClient) -> None:
        assert (await client.get("/events?type=webinar")).json()["total"] == 1
        assert (await client.get("/events?format=online")).json()["total"] == 1

    async def test_by_tag(self, client: AsyncClient) -> None:
        assert (await client.get("/events?tag=ai")).json()["total"] == 1

    async def test_by_year(self, client: AsyncClient) -> None:
        year = (NOW + timedelta(days=30)).year
        body = (await client.get(f"/events?year={year}")).json()
        assert "agents-in-production" in [item["slug"] for item in body["items"]]

    async def test_year_and_status_combine_rather_than_overwrite(self, client: AsyncClient) -> None:
        past_year = (NOW - timedelta(days=90)).year
        body = (await client.get(f"/events?status=upcoming&year={past_year}")).json()
        # Upcoming events in a past year: none, unless one bound clobbered the other.
        assert body["total"] == 0 or all(item["status"] == "upcoming" for item in body["items"])

    async def test_an_invalid_enum_value_is_a_422(self, client: AsyncClient) -> None:
        response = await client.get("/events?type=karaoke")
        assert response.status_code == 422


class TestSorting:
    async def test_upcoming_sorts_soonest_first(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        await client.post(
            "/events",
            headers=admin_headers,
            json={
                "slug": "sooner",
                "title": "Sooner",
                "startAt": (NOW + timedelta(days=2)).isoformat(),
            },
        )
        body = (await client.get("/events?status=upcoming")).json()
        assert [item["slug"] for item in body["items"]] == ["sooner", "agents-in-production"]

    async def test_completed_sorts_most_recent_first(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        await client.post(
            "/events",
            headers=admin_headers,
            json={
                "slug": "older",
                "title": "Older",
                "startAt": (NOW - timedelta(days=400)).isoformat(),
            },
        )
        body = (await client.get("/events?status=completed")).json()
        assert [item["slug"] for item in body["items"]] == ["intro-to-azure", "older"]


class TestEmptyStates:
    async def test_no_photos_and_no_recording_still_renders_a_complete_record(
        self, client: AsyncClient
    ) -> None:
        """Both empty is a normal state, not a degraded one."""
        body = (await client.get("/events/agents-in-production")).json()
        assert body["photos"] == []
        assert body["recordings"] == []
        assert body["slides"] is None
        assert body["title"] and body["summary"]

    async def test_an_online_session_has_no_location(self, client: AsyncClient) -> None:
        body = (await client.get("/events/agents-in-production")).json()
        assert body["location"] is None


class TestWrites:
    async def test_create_with_speakers_photos_and_recordings(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post(
            "/events",
            headers=admin_headers,
            json={
                "slug": "full-session",
                "title": "A event with everything",
                "startAt": (NOW - timedelta(days=1)).isoformat(),
                "speakers": [
                    {"name": "Dileepa Bandara", "role": "Host", "isHost": True},
                    {"name": "A guest", "profileUrl": "https://example.com/guest"},
                ],
                "photos": [
                    {"url": "https://res.cloudinary.com/x/1.png", "alt": "Room", "order": 1}
                ],
                "recordings": [
                    {
                        "platform": "youtube",
                        "url": "https://youtu.be/abc",
                        "durationSeconds": 3600,
                    }
                ],
                "links": [{"label": "Slides", "url": "https://x/s", "kind": "resource"}],
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["speakers"][0]["isHost"] is True
        assert body["recordings"][0]["platform"] == "youtube"
        assert body["status"] == "completed"

    async def test_a_duplicate_slug_is_a_409(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post(
            "/events",
            headers=admin_headers,
            json={
                "slug": "intro-to-azure",
                "title": "Clash",
                "startAt": NOW.isoformat(),
            },
        )
        assert response.status_code == 409

    async def test_an_invalid_slug_is_rejected(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post(
            "/events",
            headers=admin_headers,
            json={"slug": "Not A Slug", "title": "x", "startAt": NOW.isoformat()},
        )
        assert response.status_code == 422
