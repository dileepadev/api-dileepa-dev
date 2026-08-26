"""Contact-form delivery through Resend.

The API key is read at call time rather than at import, so a missing key is a
503 on `POST /contact` and not a failed startup — the rest of the API has no
business going down because email is misconfigured.
"""

from __future__ import annotations

import asyncio
import html
import logging

import resend

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.models.contact import ContactRequest

logger = logging.getLogger(__name__)


def _body(payload: ContactRequest) -> str:
    # Every field is escaped: this is user input rendered as HTML in an inbox.
    name = html.escape(payload.name)
    email = html.escape(payload.email)
    subject = html.escape(payload.subject)
    message = html.escape(payload.message).replace("\n", "<br/>")
    return (
        "<h3>New contact form submission</h3>"
        f"<p><strong>Name:</strong> {name}</p>"
        f"<p><strong>Email:</strong> {email}</p>"
        f"<p><strong>Subject:</strong> {subject}</p>"
        f"<p><strong>Message:</strong></p><p>{message}</p>"
    )


async def send_contact_email(payload: ContactRequest) -> str | None:
    settings = get_settings()
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY is not set, so the contact form cannot deliver.")
        raise ServiceUnavailableError(
            "The contact form is not accepting messages right now. "
            "Email contact@dileepa.dev directly.",
            code="email_not_configured",
        )

    resend.api_key = settings.resend_api_key
    # The SDK types this as a TypedDict; a plain dict is what it accepts.
    params: resend.Emails.SendParams = {
        "from": settings.resend_from_email,
        "to": [settings.contact_email],
        "subject": f"[Contact form] {payload.subject}",
        "html": _body(payload),
        "reply_to": payload.email,
    }

    try:
        # The Resend SDK is synchronous; run it off the event loop.
        sent = await asyncio.to_thread(resend.Emails.send, params)
    except Exception as exc:
        logger.exception("Resend rejected the contact message")
        raise ServiceUnavailableError(
            "The message could not be sent. Try again, or email contact@dileepa.dev directly.",
            code="email_send_failed",
        ) from exc

    message_id = sent.get("id") if isinstance(sent, dict) else None
    logger.info("Contact message delivered, id=%s", message_id)
    return str(message_id) if message_id else None
