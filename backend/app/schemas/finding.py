from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class FindingResponse(BaseModel):
    id:              uuid.UUID
    job_id:          uuid.UUID
    study_id:        uuid.UUID
    finding_type:    str
    rule_id:         str
    severity:        str
    domain:          str
    field:           str
    message:         str
    row_index:       int
    usubjid:         Optional[str]
    evidence:        Optional[str]
    status:          str
    resolved_by:     Optional[uuid.UUID]
    resolved_at:     Optional[datetime]
    resolution_note: Optional[str]
    created_at:      datetime

    model_config = {"from_attributes": True}


class FindingResolveRequest(BaseModel):
    status:          str            # resolved | waived
    resolution_note: Optional[str] = None
