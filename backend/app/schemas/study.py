from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class StudyCreate(BaseModel):
    study_id:         str
    title:            Optional[str] = None
    phase:            Optional[str] = None
    therapeutic_area: Optional[str] = None
    sponsor:          Optional[str] = None


class StudyUpdate(BaseModel):
    title:            Optional[str] = None
    phase:            Optional[str] = None
    therapeutic_area: Optional[str] = None
    sponsor:          Optional[str] = None
    status:           Optional[str] = None


class StudyResponse(BaseModel):
    id:               uuid.UUID
    tenant_id:        uuid.UUID
    study_id:         str
    title:            Optional[str]
    phase:            Optional[str]
    therapeutic_area: Optional[str]
    sponsor:          Optional[str]
    status:           str
    created_at:       datetime

    model_config = {"from_attributes": True}
