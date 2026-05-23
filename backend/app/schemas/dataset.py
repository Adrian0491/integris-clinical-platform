from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DatasetResponse(BaseModel):
    id:          uuid.UUID
    tenant_id:   uuid.UUID
    study_id:    uuid.UUID
    domain:      str
    filename:    str
    storage_uri: str
    file_format: str
    row_count:   Optional[int]
    uploaded_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_alias(cls, obj):
        return cls(
            id=obj.id,
            tenant_id=obj.tenant_id,
            study_id=obj.study_id,
            domain=obj.domain,
            filename=obj.filename,
            storage_uri=obj.storage_uri,
            file_format=obj.file_format,
            row_count=obj.row_count,
            uploaded_at=obj.created_at,
        )
