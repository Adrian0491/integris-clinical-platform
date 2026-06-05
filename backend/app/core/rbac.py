"""
Role-based access control FastAPI dependencies.
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import decode_access_token
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


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode JWT, load the User row, set the audit context on the session.
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

    # Store audit context directly on the session so it's accessible
    # to SQLAlchemy event listeners (ContextVar doesn't cross thread boundaries)
    db.info['audit_user_id'] = str(user.id)
    db.info['audit_tenant_id'] = str(user.tenant_id)

    return user


def require_roles(*roles: str) -> Callable[..., User]:
    allowed = set(roles) | {ROLE_SUPER_ADMIN}

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise _FORBIDDEN
        return user

    return _check


require_viewer    = require_roles(ROLE_VIEWER, ROLE_VALIDATOR, ROLE_TENANT_ADMIN)
require_validator = require_roles(ROLE_VALIDATOR, ROLE_TENANT_ADMIN)
require_admin     = require_roles(ROLE_TENANT_ADMIN)
require_super     = require_roles(ROLE_SUPER_ADMIN)