"""Contact form. Public, unauthenticated, and rate-limited harder than anything else."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.models.contact import ContactRequest, ContactResult
from app.services.email import send_contact_email

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("", response_model=ContactResult, summary="Send a message through the contact form")
@limiter.limit(get_settings().rate_limit_contact)
async def submit_contact(
    request: Request, response: Response, payload: ContactRequest
) -> ContactResult:
    """Deliver a contact-form message by email.

    `request` and `response` are unused by the handler but required by slowapi:
    it reads the caller's address off the request and writes the rate-limit
    headers onto the response.
    """
    message_id = await send_contact_email(payload)
    return ContactResult(id=message_id)
