"""
21 CFR Part 11 audit trail — implemented entirely through SQLAlchemy events.

Architecture
------------
1. Request context is stored in a ContextVar by rbac.get_current_user().
2. after_flush listener captures new/dirty/deleted rows for auditable models.
3. after_commit listener writes those entries to a separate DB session so
   they never share the fate of the main transaction.

No audit calls appear in endpoint code.

Audited models (by table name):
    studies, datasets, validation_jobs, findings,
    compliance_reports, electronic_signatures, users
"""
from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Request-scoped context
# ---------------------------------------------------------------------------

_audit_ctx: ContextVar[dict[str, Any]] = ContextVar("audit_ctx", default={})

# Guard against re-entrant flushes triggered by writing AuditLog rows.
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


def set_audit_context(
    user_id: str,
    tenant_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    _audit_ctx.set({
        "user_id":    user_id,
        "tenant_id":  tenant_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
    })


def clear_audit_context() -> None:
    _audit_ctx.set({})


def get_audit_context() -> dict[str, Any]:
    return _audit_ctx.get({})


@contextmanager
def audit_as(user_id: str, tenant_id: str):
    """Context manager for non-HTTP code (e.g. Celery tasks) that mutates data."""
    set_audit_context(user_id=user_id, tenant_id=tenant_id)
    try:
        yield
    finally:
        clear_audit_context()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _instance_hash(instance: Any) -> str:
    """SHA-256 of a sorted JSON representation of the instance's column values."""
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


def _safe_tenant(instance: Any, ctx: dict) -> str | None:
    try:
        val = getattr(instance, "tenant_id", None)
        return str(val) if val is not None else ctx.get("tenant_id")
    except Exception:
        return ctx.get("tenant_id")


# ---------------------------------------------------------------------------
# Event listeners
# ---------------------------------------------------------------------------

def register_audit_listeners(session_factory) -> None:
    """
    Register after_flush and after_commit listeners on `session_factory`.
    Call once during application startup (app/main.py).
    """

    @event.listens_for(session_factory, "after_flush")
    def _capture(session: Session, flush_context) -> None:
        # Skip if we are already inside an audit write to prevent recursion.
        if getattr(_flush_guard, "active", False):
            return

        ctx = get_audit_context()
        if not ctx.get("user_id"):
            return

        from app.models.audit import AuditLog  # late import — avoids circular

        pending: list[dict] = []

        def _record(instance: Any, action_suffix: str, before: str = "", after: str = "") -> None:
            table = getattr(instance.__class__, "__tablename__", "")
            if table not in _AUDITABLE_TABLES:
                return
            pending.append({
                "action":      f"{table}.{action_suffix}",
                "target_type": type(instance).__name__,
                "target_id":   _safe_uuid(instance),
                "tenant_id":   _safe_tenant(instance, ctx),
                "user_id":     ctx.get("user_id"),
                "ip_address":  ctx.get("ip_address"),
                "user_agent":  ctx.get("user_agent"),
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
        from app.database import SessionLocal as _SL  # fresh session

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
                    after_hash=data.get("after_hash")  or None,
                    occurred_at=datetime.now(timezone.utc),
                ))
            audit_session.commit()
        except Exception:
            audit_session.rollback()
        finally:
            _flush_guard.active = False
            audit_session.close()
