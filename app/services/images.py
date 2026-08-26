"""Cloudinary. The only image backend — Azure Blob Storage is retired.

`public_id` is deliberately caller-controlled. The blog pipeline derives it from
the repository path and uploads with `overwrite` and `invalidate`, which is what
makes the pipeline idempotent and lets the main site build image URLs without a
database lookup.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import BadRequestError, ServiceUnavailableError
from app.models.upload import UploadResult

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml"}
)
MAX_BYTES = 10 * 1024 * 1024


def _configure() -> None:
    settings = get_settings()
    if not (settings.cloudinary_cloud_name and settings.cloudinary_api_secret):
        raise ServiceUnavailableError(
            "Image uploads are not configured on this deployment.",
            code="uploads_not_configured",
        )
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


async def upload_image(
    file: UploadFile, *, folder: str | None = None, public_id: str | None = None
) -> UploadResult:
    _configure()
    settings = get_settings()

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise BadRequestError(
            f"{file.content_type or 'That file type'} is not an accepted image. "
            f"Send one of: {', '.join(sorted(ALLOWED_MIME_TYPES))}.",
            code="unsupported_image_type",
        )

    # Bounded read: one byte past the limit is enough to know the file is over
    # it, and stops an oversized upload being materialised in full first.
    # `await file.read()` with no argument reads the whole body into memory
    # before the check below could reject it, so a caller sending a multi-
    # gigabyte body could exhaust the process rather than receive a 400 — and
    # the deployment target runs in 512 MB.
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        # `file.size` is the real length, set while the multipart body was
        # parsed. The bounded read above cannot know it, so fall back to naming
        # the limit rather than reporting the truncated length as the size.
        actual = getattr(file, "size", None)
        measured = f"That image is {actual // 1024} KB" if actual else "That image is too large"
        raise BadRequestError(
            f"{measured}. The limit is {MAX_BYTES // (1024 * 1024)} MB.",
            code="image_too_large",
        )
    if not content:
        raise BadRequestError("That file is empty.", code="empty_file")

    target_folder = f"{settings.cloudinary_root_folder}/{folder or 'dileepa-dev'}"
    options: dict[str, Any] = {"folder": target_folder, "resource_type": "image"}
    if public_id:
        # A caller-supplied id makes the upload replace rather than duplicate.
        options |= {
            "public_id": public_id,
            "folder": None,
            "overwrite": True,
            "invalidate": True,
            "use_filename": False,
            "unique_filename": False,
        }

    try:
        result = await asyncio.to_thread(cloudinary.uploader.upload, content, **options)
    except Exception as exc:
        logger.exception("Cloudinary rejected an upload")
        raise ServiceUnavailableError(
            "Cloudinary would not accept that image. Try again in a moment.",
            code="upload_failed",
        ) from exc

    return UploadResult(
        url=str(result.get("secure_url", "")),
        public_id=str(result.get("public_id", "")),
        width=result.get("width"),
        height=result.get("height"),
        format=result.get("format"),
        bytes=result.get("bytes"),
    )


async def delete_image(public_id: str) -> bool:
    _configure()
    try:
        result = await asyncio.to_thread(cloudinary.uploader.destroy, public_id, invalidate=True)
    except Exception as exc:
        logger.exception("Cloudinary rejected a delete")
        raise ServiceUnavailableError(
            "Cloudinary would not delete that image. Try again in a moment.",
            code="delete_failed",
        ) from exc
    return bool(result.get("result") in {"ok", "not found"})
