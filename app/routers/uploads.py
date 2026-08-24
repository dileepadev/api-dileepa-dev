"""Uploads — the only path to Cloudinary in the whole platform.

Two callers: the admin app with a JWT, and the blog repo's workflow with the
API key. Both land here; nothing else holds Cloudinary credentials.

The path is `/uploads`. v1 served this at `/upload`, which is not carried over:
alias so the admin keeps working until Phase 5 retargets it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.core.deps import AdminUser, api_key_or_admin, repository
from app.core.errors import NotFoundError
from app.core.pagination import ListParamsDep, Page, page
from app.models.upload import UploadDeleted, UploadRecord, UploadResult
from app.repositories.base import DocumentRepository
from app.services.images import delete_image, upload_image

router = APIRouter(tags=["uploads"])

UploadsRepo = Annotated[DocumentRepository, Depends(repository("uploads"))]


async def _store(
    file: UploadFile,
    folder: str | None,
    public_id: str | None,
    repo: DocumentRepository,
) -> UploadResult:
    result = await upload_image(file, folder=folder, public_id=public_id)
    # The record is a convenience index, not the source of truth; Cloudinary is.
    # A deterministic public_id means a re-upload replaces rather than duplicates.
    await repo.upsert_by(
        "publicId",
        result.public_id,
        {
            "url": result.url,
            "publicId": result.public_id,
            "folder": folder or "",
            "fileName": file.filename,
            "mimetype": file.content_type,
            "size": result.bytes,
            "width": result.width,
            "height": result.height,
            "format": result.format,
        },
    )
    return result


@router.post(
    "/uploads",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(api_key_or_admin)],
    summary="Upload an image to Cloudinary",
)
async def create_upload(
    repo: UploadsRepo,
    file: Annotated[UploadFile, File(description="JPEG, PNG, WebP, GIF or SVG, up to 10 MB")],
    folder: Annotated[str | None, Form()] = None,
    public_id: Annotated[str | None, Form()] = None,
) -> UploadResult:
    """Upload an image.

    Pass `public_id` to make the upload idempotent: the blog pipeline derives it
    from the repository path, so re-uploading the same file replaces the asset
    and purges the CDN cache instead of creating a second copy.
    """
    return await _store(file, folder, public_id, repo)


@router.get(
    "/uploads",
    response_model=Page[UploadRecord],
    summary="List uploaded images",
)
async def list_uploads(
    params: ListParamsDep,
    _: AdminUser,
    repo: UploadsRepo,
    folder: Annotated[str | None, Query()] = None,
) -> Page[UploadRecord]:
    """List what has been uploaded, newest first."""
    filters = {"folder": folder} if folder is not None else {}
    documents, total = await repo.list(
        filters=filters,
        sort=[("createdAt", -1), ("_id", -1)],
        limit=params.limit,
        offset=params.offset,
    )
    return page([UploadRecord.model_validate(doc) for doc in documents], total, params)


@router.delete(
    "/uploads/{public_id:path}",
    response_model=UploadDeleted,
    summary="Delete an image from Cloudinary",
)
async def remove_upload(public_id: str, _: AdminUser, repo: UploadsRepo) -> UploadDeleted:
    """Delete an image from Cloudinary and drop its record.

    `public_id` is a path, because Cloudinary public IDs contain slashes.
    """
    record = await repo.find_one({"publicId": public_id})
    if record is None:
        raise NotFoundError(f"No upload with public id '{public_id}'.")
    deleted = await delete_image(public_id)
    await repo.delete_one({"publicId": public_id})
    return UploadDeleted(public_id=public_id, deleted=deleted)
