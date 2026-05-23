"""
/api/v1/auth/*  — login, logout, token refresh, TOTP MFA setup/verify.

Login flow (no MFA):
  POST /login  → {access_token, refresh_token}

Login flow (MFA enabled):
  POST /login  → {temp_token, mfa_required: true}
  POST /mfa/verify {temp_token, totp_code} → {access_token, refresh_token}
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_totp_secret,
    get_totp_provisioning_uri,
    verify_totp,
    # Re-use access token as a short-lived temp token for MFA step
    ACCESS_TOKEN,
)
from app.core.rbac import get_current_user
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user: User | None = db.query(User).filter(
        User.email == body.email.lower()
    ).first()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    tenant_id = str(user.tenant_id)
    user_id   = str(user.id)

    # If MFA is enabled, issue a temp token and require TOTP verification.
    if user.mfa_enabled and user.mfa_secret:
        temp = create_access_token(user_id, tenant_id, user.role)
        return {"mfa_required": True, "temp_token": temp}

    return TokenResponse(
        access_token=create_access_token(user_id, tenant_id, user.role),
        refresh_token=create_refresh_token(user_id, tenant_id, user.role),
    )


# ---------------------------------------------------------------------------
# MFA verification
# ---------------------------------------------------------------------------

@router.post("/mfa/verify", response_model=TokenResponse)
def mfa_verify(body: MFAVerifyRequest, db: Session = Depends(get_db)):
    from app.core.auth import decode_access_token
    try:
        payload = decode_access_token(body.temp_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    user: User | None = db.get(User, payload["sub"])
    if user is None or not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    if not verify_totp(user.mfa_secret, body.totp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code.",
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id), str(user.tenant_id), user.role),
        refresh_token=create_refresh_token(str(user.id), str(user.tenant_id), user.role),
    )


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_refresh_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    user: User | None = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    return TokenResponse(
        access_token=create_access_token(str(user.id), str(user.tenant_id), user.role),
        refresh_token=create_refresh_token(str(user.id), str(user.tenant_id), user.role),
    )


# ---------------------------------------------------------------------------
# MFA setup (authenticated)
# ---------------------------------------------------------------------------

@router.post("/mfa/setup", response_model=MFASetupResponse)
def mfa_setup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    secret = generate_totp_secret()
    uri    = get_totp_provisioning_uri(secret, current_user.email)

    current_user.mfa_secret  = secret
    current_user.mfa_enabled = False   # enabled only after first successful verify
    db.commit()

    return MFASetupResponse(secret=secret, provisioning_uri=uri)


@router.post("/mfa/confirm", response_model=MessageResponse)
def mfa_confirm(
    body: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate MFA after the user has scanned the QR code."""
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="Call /mfa/setup first.")
    if not verify_totp(current_user.mfa_secret, body.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code.")

    current_user.mfa_enabled = True
    db.commit()
    return MessageResponse(message="MFA enabled successfully.")
