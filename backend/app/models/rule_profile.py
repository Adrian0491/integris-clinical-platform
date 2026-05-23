from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, TenantScopedMixin


class RuleProfile(Base, TimestampMixin, TenantScopedMixin):
    """
    Per-tenant SDTM rule configuration.

    `overrides` is a JSONB dict mapping rule_id → {severity, enabled}.
    Example:
        {"SDTM_DM_005": {"severity": "HIGH"}, "SDTM_VS_002": {"enabled": false}}
    """
    __tablename__ = "rule_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_rule_profiles_tenant_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_profile: Mapped[str] = mapped_column(
        String(100), nullable=False, default="sdtm_default"
    )
    overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
