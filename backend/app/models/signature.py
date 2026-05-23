from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.user import User


class ElectronicSignature(Base, TenantScopedMixin):
    """
    21 CFR Part 11 electronic signature.

    Each signature records WHO signed, WHAT they signed, and WHY (meaning),
    with an HMAC hash for tamper detection.
    """
    __tablename__ = "electronic_signatures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # report | finding_resolution | dataset_lock
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    meaning: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # approved | reviewed | rejected
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # HMAC-SHA256 of (user_id + target_id + meaning + signed_at ISO8601)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    signer: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return (
            f"<ElectronicSignature id={self.id} "
            f"target_type={self.target_type!r} meaning={self.meaning!r}>"
        )
