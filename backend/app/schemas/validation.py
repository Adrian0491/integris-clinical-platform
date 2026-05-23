from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ValidationRunRequest(BaseModel):
    study_id:     uuid.UUID
    dataset_ids:  List[uuid.UUID]
    rule_profile: str = "sdtm_default"


class ValidationJobResponse(BaseModel):
    id:             uuid.UUID
    tenant_id:      uuid.UUID
    study_id:       uuid.UUID
    status:         str
    rule_profile:   str
    dataset_ids:    List[str]
    celery_task_id: Optional[str]
    started_at:     Optional[datetime]
    completed_at:   Optional[datetime]
    error_message:  Optional[str]
    created_at:     datetime

    model_config = {"from_attributes": True}


class ValidationSummary(BaseModel):
    job_id:  uuid.UUID
    total:   int
    CRIT:    int
    HIGH:    int
    MED:     int
    LOW:     int
    domains: dict[str, int]
