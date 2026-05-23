from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.study import Study
    from app.models.user import User


class Dataset(Base, TimestampMixin, TenantScopedMixin):
    """
    One uploaded file (CSV, JSON, or CDISC Dataset-JSON) per row.
    The actual file lives in GCS / local storage at gcs_uri.
    """
    __tablename__ = "datasets"

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
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    domain: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # DM | VS | AE | CM | MULTI | DATASET_JSON
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    # gs://bucket/path  or  file:///local/path
    storage_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_format: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # csv | json | dataset-json
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    study:    Mapped["Study"]       = relationship("Study", back_populates="datasets")
    uploader: Mapped["User | None"] = relationship("User",  foreign_keys=[uploaded_by])

    def __repr__(self) -> str:
        return f"<Dataset id={self.id} domain={self.domain!r} format={self.file_format!r}>"
