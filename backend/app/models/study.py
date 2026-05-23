from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.dataset import Dataset


class Study(Base, TimestampMixin, TenantScopedMixin):
    """
    A clinical trial.  STUDYID must be unique within a tenant.
    """
    __tablename__ = "studies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "study_id", name="uq_studies_tenant_study"),
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
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # SDTM STUDYID value
    study_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phase: Mapped[str | None] = mapped_column(String(20), nullable=True)  # I|II|III|IV
    therapeutic_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sponsor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active"
    )  # active | locked | archived

    # Relationships
    tenant:   Mapped["Tenant"]        = relationship("Tenant",  back_populates="studies")
    creator:  Mapped["User | None"]   = relationship("User",    foreign_keys=[created_by])
    datasets: Mapped[list["Dataset"]] = relationship("Dataset", back_populates="study")

    def __repr__(self) -> str:
        return f"<Study id={self.id} study_id={self.study_id!r}>"
