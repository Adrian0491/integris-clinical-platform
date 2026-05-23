"""
/api/v1/datasets/*  — file upload and listing.

Upload flow:
  POST /datasets/upload  multipart/form-data {file, study_id, domain}
  → saves to storage, creates Dataset row, returns DatasetResponse
"""
from __future__ import annotations

import uuid
from typing import List

import pandas as pd

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user, require_validator, require_viewer
from app.database import get_db
from app.models.dataset import Dataset
from app.models.study import Study
from app.models.user import User
from app.schemas.dataset import DatasetResponse
from app.storage.backends import get_storage

router = APIRouter(prefix="/datasets", tags=["datasets"])

ALLOWED_FORMATS = {"csv", "json", "dataset-json"}


def _detect_format(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".json"):
        return "json"
    return "json"   # default fallback


def _count_rows(data: bytes, fmt: str) -> int | None:
    try:
        if fmt == "csv":
            import io
            return len(pd.read_csv(io.BytesIO(data)))
        return None
    except Exception:
        return None


@router.post("/upload", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file:         UploadFile = File(...),
    study_id:     uuid.UUID  = Form(...),
    domain:       str        = Form(...),
    file_format:  str        = Form(None),   # auto-detected if omitted
    db:           Session    = Depends(get_db),
    current_user: User       = Depends(require_validator),
):
    # Verify the study belongs to this tenant
    study = db.query(Study).filter(
        Study.id        == study_id,
        Study.tenant_id == current_user.tenant_id,
    ).first()
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found.")

    fmt = (file_format or _detect_format(file.filename or "")).lower()
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{fmt}'. Allowed: {ALLOWED_FORMATS}",
        )

    raw = await file.read()
    storage = get_storage()
    storage_uri = storage.save(
        data=raw,
        tenant_id=str(current_user.tenant_id),
        filename=file.filename or "upload",
    )

    dataset = Dataset(
        tenant_id=current_user.tenant_id,
        study_id=study_id,
        uploaded_by=current_user.id,
        domain=domain.upper(),
        filename=file.filename or "upload",
        storage_uri=storage_uri,
        file_format=fmt,
        row_count=_count_rows(raw, fmt),
    )
    db.add(dataset)
    db.commit()
    return DatasetResponse.from_orm_alias(dataset)


@router.get("", response_model=List[DatasetResponse])
def list_datasets(
    study_id:     uuid.UUID | None = None,
    db:           Session          = Depends(get_db),
    current_user: User             = Depends(require_viewer),
):
    q = db.query(Dataset).filter(Dataset.tenant_id == current_user.tenant_id)
    if study_id:
        q = q.filter(Dataset.study_id == study_id)
    results = q.order_by(Dataset.created_at.desc()).all()
    return [DatasetResponse.from_orm_alias(d) for d in results]


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id:   uuid.UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_viewer),
):
    d = db.query(Dataset).filter(
        Dataset.id        == dataset_id,
        Dataset.tenant_id == current_user.tenant_id,
    ).first()
    if d is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return DatasetResponse.from_orm_alias(d)
