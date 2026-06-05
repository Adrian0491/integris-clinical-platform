"""
21 CFR Part 11 audit trail — implemented through SQLAlchemy events.
Audit context is stored in session.info to avoid ContextVar threading issues.
"""
from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

_flush_guard = threading.local()

_AUDITABLE_TABLES = frozenset({
    "studies",
    "datasets",
    "validation_jobs",
    "findings",
    "compliance_reports",
    "electronic_signatures",
    "users",
})


# Keep these for backward compatibility with any code that calls them
def set_audit_context(user_id: str, tenant_id: str, ip_address: str | None = None, user_agent: str | None = None) -> None:
    pass


def clear_audit_context() -> None:
    pass


def get_audit_context() -> dict[str, Any]:
    return {}


@contextmanager
def audit_as(user_id: str, tenant_id: str):
    yield


def _instance_hash(instance: Any) -> str:
    try:
        from sqlalchemy import inspect as sa_inspect
        state = sa_inspect(instance)
        data = {
            attr.key: str(getattr(instance, attr.key, None))
            for attr in state.mapper.column_attrs
            if attr.key not in ("created_at", "updated_at")
        }
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    except Exception:
        return ""


def _safe_uuid(instance: Any) -> str | None:
    try:
        val = getattr(instance, "id", None)
        return str(val) if val is not None else None
    except Exception:
        return None


def _safe_tenant(instance: Any, tenant_id: str | None) -> str | None:
    try:
        val = getattr(instance, "tenant_id", None)
        return str(val) if val is not None else tenant_id
    except Exception:
        return tenant_id


def register_audit_listeners(session_factory) -> None:
    """Register after_flush and after_commit listeners on session_factory."""

    @event.listens_for(session_factory, "after_flush")
    def _capture(session: Session, flush_context) -> None:
        if getattr(_flush_guard, "active", False):
            return

        # Read audit context from session.info instead of ContextVar
        user_id = session.info.get('audit_user_id')
        tenant_id = session.info.get('audit_tenant_id')
        ip_address = session.info.get('ip_address')
        user_agent = session.info.get('user_agent')

        if not user_id:
            return

        from app.models.audit import AuditLog

        pending: list[dict] = []

        def _record(instance: Any, action_suffix: str, before: str = "", after: str = "") -> None:
            table = getattr(instance.__class__, "__tablename__", "")
            if table not in _AUDITABLE_TABLES:
                return
            pending.append({
                "action":      f"{table}.{action_suffix}",
                "target_type": type(instance).__name__,
                "target_id":   _safe_uuid(instance),
                "tenant_id":   _safe_tenant(instance, tenant_id),
                "user_id":     user_id,
                "ip_address":  ip_address,
                "user_agent":  user_agent,
                "before_hash": before,
                "after_hash":  after,
            })

        for obj in list(session.new):
            if isinstance(obj, AuditLog):
                continue
            _record(obj, "create", after=_instance_hash(obj))

        for obj in list(session.dirty):
            if isinstance(obj, AuditLog):
                continue
            _record(obj, "update", after=_instance_hash(obj))

        for obj in list(session.deleted):
            if isinstance(obj, AuditLog):
                continue
            _record(obj, "delete", before=_instance_hash(obj))

        if pending:
            if not hasattr(session, "_audit_queue"):
                session._audit_queue = []
            session._audit_queue.extend(pending)

    @event.listens_for(session_factory, "after_commit")
    def _flush_queue(session: Session) -> None:
        queue: list[dict] = getattr(session, "_audit_queue", [])
        if not queue:
            return
        entries, session._audit_queue = queue[:], []

        from app.models.audit import AuditLog
        from app.database import SessionLocal as _SL

        audit_session = _SL()
        _flush_guard.active = True
        try:
            for data in entries:
                audit_session.add(AuditLog(
                    tenant_id=data.get("tenant_id"),
                    user_id=data.get("user_id"),
                    action=data["action"],
                    target_type=data.get("target_type"),
                    target_id=data.get("target_id"),
                    ip_address=data.get("ip_address"),
                    user_agent=data.get("user_agent"),
                    before_hash=data.get("before_hash") or None,
                    after_hash=data.get("after_hash") or None,
                    occurred_at=datetime.now(timezone.utc),
                ))
            audit_session.commit()
        except Exception:
            audit_session.rollback()
        finally:
            _flush_guard.active = False
            audit_session.close()