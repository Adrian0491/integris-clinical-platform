from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant

# Valid role values — enforced at the application layer, stored as string.
ROLE_SUPER_ADMIN   = "super_admin"
ROLE_TENANT_ADMIN  = "tenant_admin"
ROLE_VALIDATOR     = "validator"
ROLE_VIEWER        = "viewer"

ALL_ROLES = [ROLE_SUPER_ADMIN, ROLE_TENANT_ADMIN, ROLE_VALIDATOR, ROLE_VIEWER]


class User(Base, TimestampMixin, TenantScopedMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default=ROLE_VIEWER)
    # TOTP secret — stored encrypted at the application layer (Phase 2: KMS)
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
