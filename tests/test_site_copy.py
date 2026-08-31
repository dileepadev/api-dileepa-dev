"""Pillars and speaking topics — the two resources that hold website copy.

Both are `crud_router` calls, so pagination, visibility, ordering and the error
envelope are already covered by `tests/test_collections.py` against `tools`.
What is left is what is specific to these two: the closed icon set, and the
fact that a page which used to render a compiled-in constant now renders rows
in the order the admin put them in.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import users_seed
from tests.types import Headers

PILLARS: list[dict[str, Any]] = [
    {
        "title": "AI engineering",
        "description": "Agentic systems, LLM workflows, and evaluation pipelines.",
        "icon": "cpu",
        "order": 60,
    },
    {
        "title": "Open source",
        "description": "Tools, contributions, and implementations shared in public.",
        "icon": "code",
        "order": 50,
    },
    {
        "title": "Community building",
        "description": "Meetups, mentoring, and rooms where people learn to build.",
        "icon": "users",
        "order": 10,
        "published": False,
    },
]

TOPICS: list[dict[str, Any]] = [
    {
        "title": "Building production AI agents",
        "summary": "Orchestration, tool routing, and evaluation loops under real traffic.",
        "order": 40,
    },
    {
        "title": "Azure AI Foundry & enterprise AI architecture",
        "summary": "Model governance, data isolation, and scalable agent deployment.",
        "order": 30,
    },
]


@pytest.fixture
def seed() -> dict[str, list[dict[str, Any]]]:
    return {
        "users": users_seed(),
        "pillars": [dict(pillar) for pillar in PILLARS],
        "speaking_topics": [dict(topic) for topic in TOPICS],
    }


class TestPillars:
    async def test_the_cards_render_in_the_order_the_admin_set(self, client: AsyncClient) -> None:
        """The homepage used to render a constant in the site's source.

        Reordering the About section is a drag in the admin now, not a deploy,
        which is the whole reason this resource exists.
        """
        body = (await client.get("/pillars")).json()
        assert [item["title"] for item in body["items"]] == ["AI engineering", "Open source"]

    async def test_an_unpublished_card_is_not_served_publicly(self, client: AsyncClient) -> None:
        titles = [item["title"] for item in (await client.get("/pillars")).json()["items"]]
        assert "Community building" not in titles

    async def test_the_icon_is_returned_by_name(self, client: AsyncClient) -> None:
        body = (await client.get("/pillars")).json()
        assert [item["icon"] for item in body["items"]] == ["cpu", "code"]

    async def test_an_unknown_icon_is_refused(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        """The site resolves the name to an imported component.

        A name it does not know would render a card with no icon on the
        homepage and nothing anywhere to say why, so the closed set is checked
        at the boundary rather than discovered in a screenshot.
        """
        response = await client.post(
            "/pillars",
            headers=admin_headers,
            json={"title": "Woodwork", "description": "Not a pillar.", "icon": "chisel"},
        )
        assert response.status_code == 422

    async def test_a_card_written_without_an_icon_gets_the_default(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.post(
            "/pillars",
            headers=admin_headers,
            json={"title": "Technical writing", "description": "Notes on how it went."},
        )
        assert response.status_code == 201
        assert response.json()["icon"] == "cpu"


class TestSpeakingTopics:
    async def test_the_talk_themes_are_public_and_ordered(self, client: AsyncClient) -> None:
        body = (await client.get("/speaking-topics")).json()
        assert [item["title"] for item in body["items"]] == [t["title"] for t in TOPICS]
        assert body["items"][0]["summary"] == TOPICS[0]["summary"]

    async def test_the_path_is_hyphenated_not_underscored(self, client: AsyncClient) -> None:
        # `speaking_topics` is the collection; a URL is not the place to read
        # snake_case, and pinning it here stops the two being conflated.
        assert (await client.get("/speaking_topics")).status_code == 404

    async def test_writes_need_a_token(self, client: AsyncClient) -> None:
        response = await client.post(
            "/speaking-topics", json={"title": "Uninvited", "summary": "Should not work."}
        )
        assert response.status_code == 401

    async def test_create_and_delete(self, client: AsyncClient, admin_headers: Headers) -> None:
        created = await client.post(
            "/speaking-topics",
            headers=admin_headers,
            json={
                "title": "Production LLM pipelines & evaluation harnesses",
                "summary": "From experimental prompts to systems with measurable performance.",
                "order": 20,
            },
        )
        assert created.status_code == 201
        topic_id = created.json()["id"]

        assert (await client.get(f"/speaking-topics/{topic_id}")).status_code == 200

        deleted = await client.delete(f"/speaking-topics/{topic_id}", headers=admin_headers)
        assert deleted.status_code == 200
        assert (await client.get(f"/speaking-topics/{topic_id}")).status_code == 404
