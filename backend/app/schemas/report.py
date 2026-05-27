"""
Pydantic schemas for compliance reports.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReportGenerateRequest(BaseModel):
    job_id: uuid.UUID
    report_type: str = "sdtm_validation"  # sdtm_validation | anomaly | executive


class ReportSignRequest(BaseModel):
    pass  # signature is applied from current_user context


class ComplianceReportResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    job_id: uuid.UUID
    study_id: uuid.UUID
    report_type: str
    storage_uri: str | None
    generated_by: uuid.UUID | None
    signed_at: datetime | None
    signed_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}