"""Blog comments.

Comments post without review, so most of what is worth testing is what stops a
bad one — and what stops a good one leaking something it should not.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import users_seed
from tests.types import Headers

SLUG = "2026-08-06-part-1-kicking-off-the-series"


@pytest.fixture
def seed() -> dict[str, list[dict[str, Any]]]:
    return {
        "users": users_seed(),
        "blogs": [
            {
                "slug": SLUG,
                "title": "Kicking off the series",
                "publishedDate": "2026-08-06T00:00:00Z",
                "published": True,
            },
            {
                "slug": "a-hidden-post",
                "title": "Hidden",
                "publishedDate": "2026-08-06T00:00:00Z",
                "published": False,
            },
        ],
    }


async def post_comment(client: AsyncClient, **overrides: Any) -> Any:
    body = {"author": "Anna", "body": "Useful walkthrough, thanks.", **overrides}
    return await client.post(f"/blogs/{SLUG}/comments", json=body)


class TestPosting:
    async def test_a_comment_appears_immediately(self, client: AsyncClient) -> None:
        """No approval queue: what is posted is what is readable."""
        created = await post_comment(client)
        assert created.status_code == 201
        assert created.json()["accepted"] is True

        threads = await client.get(f"/blogs/{SLUG}/comments")
        assert [t["comment"]["author"] for t in threads.json()] == ["Anna"]

    async def test_the_slug_comes_from_the_path_not_the_body(self, client: AsyncClient) -> None:
        """A comment cannot be aimed at a post other than the one it was left on.

        `CommentCreate` has no `slug` field and `ApiModel` forbids extra ones, so
        an attempt to name a different post is a 422 rather than a value that
        gets quietly ignored — which is the stronger of the two behaviours.
        """
        response = await post_comment(client, slug="a-hidden-post")
        assert response.status_code == 422

        threads = await client.get(f"/blogs/{SLUG}/comments")
        assert threads.json() == []

    async def test_commenting_on_an_unknown_post_is_a_404(self, client: AsyncClient) -> None:
        response = await client.post(
            "/blogs/no-such-post/comments", json={"author": "A", "body": "Hi"}
        )
        assert response.status_code == 404

    async def test_commenting_on_an_unpublished_post_is_a_404(self, client: AsyncClient) -> None:
        response = await client.post(
            "/blogs/a-hidden-post/comments", json={"author": "A", "body": "Hi"}
        )
        assert response.status_code == 404

    async def test_an_empty_body_is_rejected(self, client: AsyncClient) -> None:
        response = await post_comment(client, body="")
        assert response.status_code == 422

    async def test_an_overlong_body_is_rejected(self, client: AsyncClient) -> None:
        response = await post_comment(client, body="x" * 4001)
        assert response.status_code == 422

    async def test_whitespace_is_stripped(self, client: AsyncClient) -> None:
        await post_comment(client, author="  Anna  ", body="  Hello  ")
        threads = await client.get(f"/blogs/{SLUG}/comments")
        comment = threads.json()[0]["comment"]
        assert comment["author"] == "Anna"
        assert comment["body"] == "Hello"


class TestHoneypot:
    async def test_a_honeypot_hit_looks_exactly_like_success(self, client: AsyncClient) -> None:
        """201, not 400. Telling a bot which field caught it is how it learns."""
        response = await post_comment(client, honeypot="http://spam.example")
        assert response.status_code == 201

    async def test_a_honeypot_hit_stores_nothing(self, client: AsyncClient) -> None:
        await post_comment(client, honeypot="http://spam.example")
        threads = await client.get(f"/blogs/{SLUG}/comments")
        assert threads.json() == []


class TestThreading:
    async def test_a_reply_nests_under_its_parent(self, client: AsyncClient) -> None:
        parent = (await post_comment(client, author="Anna")).json()["comment"]
        await post_comment(client, author="Sam", parentId=parent["id"])

        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert len(threads) == 1
        assert threads[0]["comment"]["author"] == "Anna"
        assert [r["author"] for r in threads[0]["replies"]] == ["Sam"]

    async def test_depth_is_capped_at_one(self, client: AsyncClient) -> None:
        """A reply to a reply joins the thread rather than starting a third level.

        Rejecting it would punish the reader for a structural rule they cannot
        see; re-parenting puts the comment where it belongs.
        """
        parent = (await post_comment(client, author="Anna")).json()["comment"]
        reply = (await post_comment(client, author="Sam", parentId=parent["id"])).json()["comment"]
        await post_comment(client, author="Raj", parentId=reply["id"])

        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert len(threads) == 1
        assert [r["author"] for r in threads[0]["replies"]] == ["Sam", "Raj"]

    async def test_a_reply_to_another_posts_comment_is_not_honoured(
        self, client: AsyncClient
    ) -> None:
        """The parent must live on the same post, or the reply goes top level."""
        foreign = (await post_comment(client, author="Anna")).json()["comment"]
        await client.post(
            "/blogs/a-hidden-post/comments",
            json={"author": "Sam", "body": "Hi", "parentId": foreign["id"]},
        )
        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert threads[0]["replies"] == []

    async def test_an_unknown_parent_becomes_a_top_level_comment(self, client: AsyncClient) -> None:
        await post_comment(client, author="Sam", parentId="507f1f77bcf86cd799439011")
        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert len(threads) == 1
        assert threads[0]["comment"]["author"] == "Sam"


class TestPrivacy:
    """The email a commenter gives is never handed back to a reader."""

    async def test_the_public_thread_carries_no_email(self, client: AsyncClient) -> None:
        await post_comment(client, email="anna@example.com")
        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert "email" not in threads[0]["comment"]

    async def test_the_post_response_carries_no_email(self, client: AsyncClient) -> None:
        created = await post_comment(client, email="anna@example.com")
        assert "email" not in created.json()["comment"]

    async def test_the_public_thread_carries_no_visitor_key(self, client: AsyncClient) -> None:
        await post_comment(client)
        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert "key" not in threads[0]["comment"]

    async def test_listing_comments_requires_a_token(self, client: AsyncClient) -> None:
        """`/comments` is the one collection an anonymous caller cannot list.

        `crud_router` would have made this route public, like /projects and
        /events. It holds email addresses, so it is written out instead.
        """
        response = await client.get("/comments")
        assert response.status_code == 401

    async def test_an_admin_does_see_the_email(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        await post_comment(client, email="anna@example.com")
        listing = await client.get("/comments", headers=admin_headers)
        assert listing.status_code == 200
        assert listing.json()["items"][0]["email"] == "anna@example.com"


class TestModeration:
    async def test_hiding_removes_a_comment_from_the_public_thread(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        created = (await post_comment(client)).json()["comment"]
        hidden = await client.patch(
            f"/comments/{created['id']}",
            headers=admin_headers,
            json={"published": False},
        )
        assert hidden.status_code == 200

        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert threads == []

    async def test_hiding_a_parent_promotes_its_replies(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        """A reply outlives the comment above it.

        Losing a reply because someone removed its parent destroys a
        contribution that the reply's author is not responsible for.
        """
        parent = (await post_comment(client, author="Anna")).json()["comment"]
        await post_comment(client, author="Sam", parentId=parent["id"])
        await client.patch(
            f"/comments/{parent['id']}", headers=admin_headers, json={"published": False}
        )

        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert [t["comment"]["author"] for t in threads] == ["Sam"]

    async def test_deleting_a_comment_removes_it(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        created = (await post_comment(client)).json()["comment"]
        deleted = await client.delete(f"/comments/{created['id']}", headers=admin_headers)
        assert deleted.status_code == 204
        assert (await client.get(f"/blogs/{SLUG}/comments")).json() == []

    async def test_moderation_requires_a_token(self, client: AsyncClient) -> None:
        created = (await post_comment(client)).json()["comment"]
        assert (
            await client.patch(f"/comments/{created['id']}", json={"published": False})
        ).status_code == 401
        assert (await client.delete(f"/comments/{created['id']}")).status_code == 401


class TestAuthorReplies:
    """The owner replying in their own thread, from the admin."""

    async def test_an_admin_reply_is_marked_as_the_author(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        parent = (await post_comment(client, author="Anna")).json()["comment"]
        created = await client.post(
            "/comments",
            headers=admin_headers,
            json={
                "slug": SLUG,
                "author": "Dileepa",
                "body": "Glad it helped.",
                "parentId": parent["id"],
            },
        )
        assert created.status_code == 201

        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        reply = threads[0]["replies"][0]
        assert reply["author"] == "Dileepa"
        assert reply["authorIsOwner"] is True

    async def test_a_reader_cannot_claim_the_author_badge(self, client: AsyncClient) -> None:
        """`CommentCreate` has no such field, and extra fields are forbidden.

        The distinction is enforced by the shape of the request rather than by a
        check that could be forgotten.
        """
        response = await post_comment(client, authorIsOwner=True)
        assert response.status_code == 422

    async def test_a_reader_comment_is_not_marked_as_the_author(self, client: AsyncClient) -> None:
        await post_comment(client)
        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert threads[0]["comment"]["authorIsOwner"] is False

    async def test_replying_requires_a_token(self, client: AsyncClient) -> None:
        response = await client.post(
            "/comments", json={"slug": SLUG, "author": "Nobody", "body": "Hi"}
        )
        assert response.status_code == 401


class TestCommentReactions:
    """The same four reactions as a post, on comments and on replies alike."""

    async def test_reacting_to_a_comment_counts(self, client: AsyncClient) -> None:
        created = (await post_comment(client)).json()["comment"]
        response = await client.post(
            f"/blogs/{SLUG}/comments/{created['id']}/reactions",
            json={"reaction": "insightful"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["reactions"]["insightful"] == 1
        assert body["viewerReaction"] == "insightful"

    async def test_a_reply_can_be_reacted_to(self, client: AsyncClient) -> None:
        """Replies are comments, so this needs no second route."""
        parent = (await post_comment(client, author="Anna")).json()["comment"]
        reply = (await post_comment(client, author="Sam", parentId=parent["id"])).json()["comment"]
        response = await client.post(
            f"/blogs/{SLUG}/comments/{reply['id']}/reactions",
            json={"reaction": "liked"},
        )
        assert response.json()["reactions"]["liked"] == 1

    async def test_changing_a_reaction_moves_the_count(self, client: AsyncClient) -> None:
        created = (await post_comment(client)).json()["comment"]
        url = f"/blogs/{SLUG}/comments/{created['id']}/reactions"
        await client.post(url, json={"reaction": "liked"})
        body = (await client.post(url, json={"reaction": "useful"})).json()
        assert body["reactions"]["liked"] == 0
        assert body["reactions"]["useful"] == 1

    async def test_pressing_the_same_reaction_clears_it(self, client: AsyncClient) -> None:
        created = (await post_comment(client)).json()["comment"]
        url = f"/blogs/{SLUG}/comments/{created['id']}/reactions"
        await client.post(url, json={"reaction": "learned"})
        body = (await client.post(url, json={"reaction": "learned"})).json()
        assert body["reactions"]["learned"] == 0
        assert body["viewerReaction"] is None

    async def test_the_thread_reports_what_this_reader_chose(self, client: AsyncClient) -> None:
        """Read back in one query across the thread, not one per comment."""
        first = (await post_comment(client, author="Anna")).json()["comment"]
        second = (await post_comment(client, author="Raj")).json()["comment"]
        await client.post(
            f"/blogs/{SLUG}/comments/{first['id']}/reactions",
            json={"reaction": "useful"},
        )

        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        by_id = {t["comment"]["id"]: t["comment"] for t in threads}
        assert by_id[first["id"]]["viewerReaction"] == "useful"
        assert by_id[second["id"]]["viewerReaction"] is None

    async def test_reacting_through_the_wrong_post_is_a_404(self, client: AsyncClient) -> None:
        """The slug in the path is checked against the comment, not decorative."""
        created = (await post_comment(client)).json()["comment"]
        response = await client.post(
            f"/blogs/a-hidden-post/comments/{created['id']}/reactions",
            json={"reaction": "liked"},
        )
        assert response.status_code == 404

    async def test_reacting_to_an_unknown_comment_is_a_404(self, client: AsyncClient) -> None:
        response = await client.post(
            f"/blogs/{SLUG}/comments/507f1f77bcf86cd799439011/reactions",
            json={"reaction": "liked"},
        )
        assert response.status_code == 404

    async def test_reacting_to_a_hidden_comment_is_a_404(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        created = (await post_comment(client)).json()["comment"]
        await client.patch(
            f"/comments/{created['id']}", headers=admin_headers, json={"published": False}
        )
        response = await client.post(
            f"/blogs/{SLUG}/comments/{created['id']}/reactions",
            json={"reaction": "liked"},
        )
        assert response.status_code == 404

    async def test_an_unknown_reaction_is_rejected(self, client: AsyncClient) -> None:
        created = (await post_comment(client)).json()["comment"]
        response = await client.post(
            f"/blogs/{SLUG}/comments/{created['id']}/reactions",
            json={"reaction": "fire"},
        )
        assert response.status_code == 422

    async def test_a_comment_reaction_never_goes_negative(self, client: AsyncClient) -> None:
        created = (await post_comment(client)).json()["comment"]
        url = f"/blogs/{SLUG}/comments/{created['id']}/reactions"
        await client.post(url, json={"reaction": "liked"})
        await client.post(url, json={"reaction": None})
        await client.post(url, json={"reaction": None})

        threads = (await client.get(f"/blogs/{SLUG}/comments")).json()
        assert threads[0]["comment"]["reactions"]["liked"] == 0

    async def test_the_public_comment_still_carries_no_email(self, client: AsyncClient) -> None:
        """The reaction response is a PublicComment, so the guarantee holds here too."""
        created = (await post_comment(client, email="anna@example.com")).json()["comment"]
        response = await client.post(
            f"/blogs/{SLUG}/comments/{created['id']}/reactions",
            json={"reaction": "liked"},
        )
        assert "email" not in response.json()
