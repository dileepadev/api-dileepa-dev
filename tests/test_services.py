"""Contact and uploads, with the external services faked.

`AGENTS.md`: no live API keys and no network in a unit test. Resend and
Cloudinary are patched at the boundary; everything in front of them is real.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from httpx import AsyncClient
from starlette.datastructures import Headers as DatastructureHeaders

from app.core.errors import ServiceUnavailableError
from app.models.upload import UploadResult
from tests.types import Headers, Repos


class TestContact:
    async def test_sends_and_reports_the_message_id(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: dict[str, Any] = {}

        def fake_send(params: dict[str, Any]) -> dict[str, str]:
            sent.update(params)
            return {"id": "msg_123"}

        monkeypatch.setattr("resend.Emails.send", fake_send)
        monkeypatch.setenv("RESEND_API_KEY", "test-key")
        from app.core.config import get_settings

        get_settings.cache_clear()

        response = await client.post(
            "/contact",
            json={
                "name": "A Visitor",
                "email": "visitor@example.com",
                "subject": "Hello",
                "message": "Line one\nLine two",
            },
        )
        assert response.status_code == 200
        assert response.json()["id"] == "msg_123"
        assert sent["reply_to"] == "visitor@example.com"
        assert sent["subject"] == "[Contact form] Hello"

    async def test_html_in_a_message_is_escaped(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: dict[str, Any] = {}
        monkeypatch.setattr("resend.Emails.send", lambda params: sent.update(params) or {"id": "x"})
        monkeypatch.setenv("RESEND_API_KEY", "test-key")
        from app.core.config import get_settings

        get_settings.cache_clear()

        await client.post(
            "/contact",
            json={
                "name": "<script>alert(1)</script>",
                "email": "visitor@example.com",
                "subject": "Hi",
                "message": "<img src=x onerror=alert(1)>",
            },
        )
        assert "<script>" not in sent["html"]
        assert "&lt;script&gt;" in sent["html"]

    async def test_a_missing_api_key_is_a_503_with_a_way_forward(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RESEND_API_KEY", "")
        from app.core.config import get_settings

        get_settings.cache_clear()

        response = await client.post(
            "/contact",
            json={
                "name": "A Visitor",
                "email": "visitor@example.com",
                "subject": "Hi",
                "message": "Hello",
            },
        )
        assert response.status_code == 503
        assert "contact@dileepa.dev" in response.json()["error"]["message"]

    async def test_validation(self, client: AsyncClient) -> None:
        response = await client.post("/contact", json={"name": "", "email": "nope"})
        assert response.status_code == 422


class TestUploads:
    @pytest.fixture(autouse=True)
    def fake_cloudinary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_upload(
            file: Any, *, folder: str | None = None, public_id: str | None = None
        ) -> UploadResult:
            return UploadResult(
                url=f"https://res.cloudinary.com/x/image/upload/v1/{public_id or file.filename}",
                public_id=public_id or "generated/id",
                width=1200,
                height=630,
                format="png",
                bytes=1024,
            )

        async def fake_delete(public_id: str) -> bool:
            return True

        monkeypatch.setattr("app.routers.uploads.upload_image", fake_upload)
        monkeypatch.setattr("app.routers.uploads.delete_image", fake_delete)

    def png(self) -> tuple[str, io.BytesIO, str]:
        return ("banner.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")

    async def test_admin_can_upload(self, client: AsyncClient, admin_headers: Headers) -> None:
        response = await client.post("/uploads", headers=admin_headers, files={"file": self.png()})
        assert response.status_code == 201
        assert response.json()["publicId"] == "generated/id"

    async def test_the_pipeline_can_upload_with_its_api_key(
        self, client: AsyncClient, api_key_headers: Headers
    ) -> None:
        response = await client.post(
            "/uploads",
            headers=api_key_headers,
            files={"file": self.png()},
            data={"public_id": "blog/banners/2026-09-01-a-new-post"},
        )
        assert response.status_code == 201
        assert response.json()["publicId"] == "blog/banners/2026-09-01-a-new-post"

    async def test_a_deterministic_public_id_replaces_rather_than_duplicates(
        self, client: AsyncClient, api_key_headers: Headers, repositories: Repos
    ) -> None:
        for _ in range(2):
            await client.post(
                "/uploads",
                headers=api_key_headers,
                files={"file": self.png()},
                data={"public_id": "blog/banners/same"},
            )
        assert await repositories["uploads"].count({"publicId": "blog/banners/same"}) == 1

    async def test_anonymous_uploads_are_rejected(self, client: AsyncClient) -> None:
        response = await client.post("/uploads", files={"file": self.png()})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "missing_credentials"

    async def test_the_v1_path_is_gone(self, client: AsyncClient, admin_headers: Headers) -> None:
        # Not aliased: the admin app moves to /uploads in the same release.
        response = await client.post("/upload", headers=admin_headers, files={"file": self.png()})
        assert response.status_code == 404

    async def test_listing_needs_admin(self, client: AsyncClient, editor_headers: Headers) -> None:
        assert (await client.get("/uploads", headers=editor_headers)).status_code == 403

    async def test_delete(
        self, client: AsyncClient, admin_headers: Headers, api_key_headers: Headers
    ) -> None:
        await client.post(
            "/uploads",
            headers=api_key_headers,
            files={"file": self.png()},
            data={"public_id": "blog/banners/deleteme"},
        )
        response = await client.delete("/uploads/blog/banners/deleteme", headers=admin_headers)
        assert response.status_code == 200
        assert response.json() == {"publicId": "blog/banners/deleteme", "deleted": True}

    async def test_deleting_something_absent_is_a_404(
        self, client: AsyncClient, admin_headers: Headers
    ) -> None:
        response = await client.delete("/uploads/nothing/here", headers=admin_headers)
        assert response.status_code == 404


class TestImageValidation:
    """The guards in the service itself, tested without a Cloudinary account."""

    async def test_an_unsupported_type_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import UploadFile

        from app.core.errors import BadRequestError
        from app.services import images

        monkeypatch.setattr(images, "_configure", lambda: None)
        upload = UploadFile(
            filename="notes.pdf",
            file=io.BytesIO(b"%PDF"),
            headers=DatastructureHeaders({"content-type": "application/pdf"}),
        )
        with pytest.raises(BadRequestError):
            await images.upload_image(upload)

    async def test_an_oversized_image_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import UploadFile

        from app.core.errors import BadRequestError
        from app.services import images

        monkeypatch.setattr(images, "_configure", lambda: None)
        oversized = b"x" * (images.MAX_BYTES + 1024)
        upload = UploadFile(
            filename="huge.png",
            file=io.BytesIO(oversized),
            size=len(oversized),
            headers=DatastructureHeaders({"content-type": "image/png"}),
        )
        with pytest.raises(BadRequestError) as caught:
            await images.upload_image(upload)
        assert caught.value.code == "image_too_large"

    async def test_an_oversized_image_is_not_read_into_memory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The read is bounded, so the body never lands in RAM in full.

        This is the guard, not the 400 above: an unbounded read would still
        reject the file, but only after materialising all of it — which on a
        512 MB deployment is the process rather than the request.
        """
        from fastapi import UploadFile

        from app.core.errors import BadRequestError
        from app.services import images

        monkeypatch.setattr(images, "_configure", lambda: None)

        requested: list[int] = []

        class RecordingBytesIO(io.BytesIO):
            # Signature matches BytesIO.read, which accepts None as "read all".
            def read(self, size: int | None = -1, /) -> bytes:
                requested.append(-1 if size is None else size)
                return super().read(size)

        oversized = b"x" * (images.MAX_BYTES * 4)
        upload = UploadFile(
            filename="huge.png",
            file=RecordingBytesIO(oversized),
            size=len(oversized),
            headers=DatastructureHeaders({"content-type": "image/png"}),
        )
        with pytest.raises(BadRequestError):
            await images.upload_image(upload)

        assert requested, "the service never read the upload"
        assert -1 not in requested, "an unbounded read would pull the whole body into memory"
        assert max(requested) <= images.MAX_BYTES + 1

    async def test_an_empty_file_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi import UploadFile

        from app.core.errors import BadRequestError
        from app.services import images

        monkeypatch.setattr(images, "_configure", lambda: None)
        upload = UploadFile(
            filename="empty.png",
            file=io.BytesIO(b""),
            size=0,
            headers=DatastructureHeaders({"content-type": "image/png"}),
        )
        with pytest.raises(BadRequestError) as caught:
            await images.upload_image(upload)
        assert caught.value.code == "empty_file"

    async def test_missing_configuration_is_a_503(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import get_settings
        from app.services import images

        monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "")
        monkeypatch.setenv("CLOUDINARY_API_SECRET", "")
        get_settings.cache_clear()
        with pytest.raises(ServiceUnavailableError):
            images._configure()
