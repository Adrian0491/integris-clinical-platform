from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.finding import Finding
    from app.models.user import User


class ValidationJob(Base, TimestampMixin, TenantScopedMixin):
    """
    An async validation run submitted by a user.
    Celery processes it in the background; status reflects progress.
    """
    __tablename__ = "validation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    study_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # JSON array of Dataset UUIDs (stored as TEXT[] in PostgreSQL)
    dataset_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    rule_profile: Mapped[str] = mapped_column(
        String(100), nullable=False, default="sdtm_default"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )  # queued | running | completed | failed
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    submitter: Mapped["User | None"] = relationship("User", foreign_keys=[submitted_by])
    findings:  Mapped[list["Finding"]] = relationship("Finding", back_populates="job")

    def __repr__(self) -> str:
        return f"<ValidationJob id={self.id} status={self.status!r}>"
