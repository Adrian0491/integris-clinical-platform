"""
/api/v1/audit/*  — read-only audit trail endpoint (21 CFR Part 11).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.rbac import require_viewer
from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import User
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    user_id: uuid.UUID | None
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    ip_address: str | None
    user_agent: str | None
    before_hash: str | None
    after_hash: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    action: str | None = None,
    user_id: uuid.UUID | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """List audit log entries for the current tenant."""
    q = db.query(AuditLog).filter(
        AuditLog.tenant_id == current_user.tenant_id
    )

    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if from_date:
        q = q.filter(AuditLog.occurred_at >= from_date)
    if to_date:
        q = q.filter(AuditLog.occurred_at <= to_date)

    return q.order_by(AuditLog.occurred_at.desc()).offset(offset).limit(limit).all()