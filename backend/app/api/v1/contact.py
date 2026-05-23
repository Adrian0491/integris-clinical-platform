"""
POST /api/v1/contact  — public contact form submission.

No authentication required. Validates input, logs the submission,
and returns a confirmation. In production, hook this to an email
service (SendGrid, Postmark, etc.) or a CRM.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contact", tags=["public"])


class ContactRequest(BaseModel):
    name:    str       = Field(..., min_length=1, max_length=200)
    email:   EmailStr
    message: str       = Field(..., min_length=10, max_length=5000)


class ContactResponse(BaseModel):
    status: str


@router.post("", response_model=ContactResponse, status_code=200)
def submit_contact(body: ContactRequest) -> ContactResponse:
    """
    Accept a contact form submission from the public landing page.

    Logs name + email (never logs the full message body to avoid
    accidental PII capture in Cloud Logging).
    """
    logger.info(
        "Contact form submission received",
        extra={
            "name":  body.name,
            "email": body.email,
            "msg_length": len(body.message),
        },
    )
    # TODO: forward to SendGrid / Postmark / HubSpot in v1.0
    return ContactResponse(status="received")
