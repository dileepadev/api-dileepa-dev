"""Uploads.

`POST /uploads` is the only path to Cloudinary; nothing else in the platform
holds Cloudinary credentials.
"""

from __future__ import annotations

from app.models.common import ApiModel, TimestampedResource, Url


class UploadResult(ApiModel):
    url: Url
    public_id: str
    width: int | None = None
    height: int | None = None
    format: str | None = None
    bytes: int | None = None


class UploadRecord(TimestampedResource):
    url: Url
    public_id: str
    folder: str = ""
    file_name: str | None = None
    mimetype: str | None = None
    size: int | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None


class UploadDeleted(ApiModel):
    public_id: str
    deleted: bool
