"""
Role-based access control FastAPI dependencies.

Usage in endpoints:
    @router.get("/studies")
    def list_studies(user: User = Depends(require_roles(ROLE_VIEWER, ROLE_VALIDATOR))):
        ...

The injection chain for every protected endpoint is:
    HTTP Bearer token
      → decode_access_token()
      → load User from DB
      → set audit context (user_id, tenant_id, ip, user-agent)
      → optional role check
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import decode_access_token
from app.core.audit import set_audit_context
from app.database import get_db
from app.models.user import (
    ALL_ROLES,
    ROLE_SUPER_ADMIN,
    ROLE_TENANT_ADMIN,
    ROLE_VALIDATOR,
    ROLE_VIEWER,
    User,
)

_bearer = HTTPBearer(auto_error=True)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)
_INACTIVE = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Account is inactive.",
)
_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Insufficient permissions.",
)


# ---------------------------------------------------------------------------
# Core user resolver
# ---------------------------------------------------------------------------

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode JWT, load the User row, set the audit context for this request.
    Raises 401 for invalid/expired tokens and inactive users.
    """
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise _UNAUTHORIZED

    user = db.get(User, user_id)
    if user is None:
        raise _UNAUTHORIZED
    if not user.is_active:
        raise _INACTIVE

    # Propagate request context to the audit listener (core/audit.py)
    set_audit_context(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return user


# ---------------------------------------------------------------------------
# Role-gated dependency factory
# ---------------------------------------------------------------------------

def require_roles(*roles: str) -> Callable[..., User]:
    """
    Returns a FastAPI dependency that allows only users with one of the
    specified roles.  Always includes super_admin.

    Example:
        Depends(require_roles(ROLE_TENANT_ADMIN, ROLE_VALIDATOR))
    """
    allowed = set(roles) | {ROLE_SUPER_ADMIN}

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise _FORBIDDEN
        return user

    return _check


# ---------------------------------------------------------------------------
# Convenience pre-built dependencies
# ---------------------------------------------------------------------------

# Any authenticated user (viewer and above)
require_viewer    = require_roles(ROLE_VIEWER, ROLE_VALIDATOR, ROLE_TENANT_ADMIN)
# Can run validations and manage datasets
require_validator = require_roles(ROLE_VALIDATOR, ROLE_TENANT_ADMIN)
# Can manage users, studies, settings within the tenant
require_admin     = require_roles(ROLE_TENANT_ADMIN)
# Only Anthropic super-admins (multi-tenant management)
require_super     = require_roles(ROLE_SUPER_ADMIN)
