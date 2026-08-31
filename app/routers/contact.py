"""Contact form. Public, unauthenticated, and rate-limited harder than anything else."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import get_settings
from app.core.deps import repository
from app.core.rate_limit import limiter
from app.models.contact import ContactRequest, ContactResult
from app.repositories.base import DocumentRepository
from app.services.email import send_contact_email

router = APIRouter(prefix="/contact", tags=["contact"])

ContactsRepo = Annotated[DocumentRepository, Depends(repository("contacts"))]


@router.post("", response_model=ContactResult, summary="Send a message through the contact form")
@limiter.limit(get_settings().rate_limit_contact)
async def submit_contact(
    request: Request,
    response: Response,
    payload: ContactRequest,
    contacts_repo: ContactsRepo,
) -> ContactResult:
    """Deliver a contact-form message by email and persist it to the database.

    `request` and `response` are unused by the handler but required by slowapi:
    it reads the caller's address off the request and writes the rate-limit
    headers onto the response.
    """
    await contacts_repo.create(payload.model_dump())
    message_id = await send_contact_email(payload)
    return ContactResult(id=message_id)
