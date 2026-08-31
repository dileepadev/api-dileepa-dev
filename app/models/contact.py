"""Contact form."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.models.common import ApiModel, TimestampedResource


class ContactRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=5000)


class ContactResult(ApiModel):
    success: bool = True
    message: str = "Message sent."
    id: str | None = None


class ContactMessage(TimestampedResource):
    name: str
    email: EmailStr
    subject: str
    message: str
