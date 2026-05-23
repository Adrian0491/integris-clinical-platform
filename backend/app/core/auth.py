"""
JWT token creation / validation and TOTP MFA helpers.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pyotp

from app.config import get_settings
from app.core.security import get_private_key_pem, get_public_key_pem

settings = get_settings()

# Token types — stored in the `type` claim
ACCESS_TOKEN  = "access"
REFRESH_TOKEN = "refresh"


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def _build_payload(
    subject: str,
    token_type: str,
    tenant_id: str,
    role: str,
    expires_delta: timedelta,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub":       subject,
        "type":      token_type,
        "tenant_id": tenant_id,
        "role":      role,
        "jti":       str(uuid.uuid4()),  # unique token ID (for future revocation)
        "iat":       now,
        "exp":       now + expires_delta,
    }
    if extra:
        payload.update(extra)
    return payload


def create_access_token(user_id: str, tenant_id: str, role: str) -> str:
    payload = _build_payload(
        subject=user_id,
        token_type=ACCESS_TOKEN,
        tenant_id=tenant_id,
        role=role,
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return jwt.encode(payload, get_private_key_pem(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str, tenant_id: str, role: str) -> str:
    payload = _build_payload(
        subject=user_id,
        token_type=REFRESH_TOKEN,
        tenant_id=tenant_id,
        role=role,
        expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return jwt.encode(payload, get_private_key_pem(), algorithm=settings.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

def _decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            get_public_key_pem(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired.")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


def decode_access_token(token: str) -> dict[str, Any]:
    payload = _decode_token(token)
    if payload.get("type") != ACCESS_TOKEN:
        raise ValueError("Token is not an access token.")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = _decode_token(token)
    if payload.get("type") != REFRESH_TOKEN:
        raise ValueError("Token is not a refresh token.")
    return payload


# ---------------------------------------------------------------------------
# TOTP MFA helpers
# ---------------------------------------------------------------------------

def generate_totp_secret() -> str:
    """Generate a new TOTP secret for a user."""
    return pyotp.random_base32()


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    """Return an otpauth:// URI for QR code display."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.APP_NAME)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code.  Allows a 30-second window."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
