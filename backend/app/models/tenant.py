from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.study import Study


class Tenant(Base, TimestampMixin):
    """
    One row per CRO / pharma sponsor customer.
    All other tables are scoped to a tenant via tenant_id FK.
    """
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(
        String(50), nullable=False, default="trial"
    )  # trial | professional | enterprise
    hipaa_baa_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    users:   Mapped[list["User"]]  = relationship("User",  back_populates="tenant")
    studies: Mapped[list["Study"]] = relationship("Study", back_populates="tenant")

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug!r}>"
