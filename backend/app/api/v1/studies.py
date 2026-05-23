"""
/api/v1/studies/*  — CRUD for clinical studies (scoped to the caller's tenant).
"""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user, require_admin, require_validator, require_viewer
from app.database import get_db
from app.models.study import Study
from app.models.user import User
from app.schemas.study import StudyCreate, StudyResponse, StudyUpdate

router = APIRouter(prefix="/studies", tags=["studies"])


def _get_study_or_404(study_uuid: uuid.UUID, tenant_id: uuid.UUID, db: Session) -> Study:
    study = db.query(Study).filter(
        Study.id == study_uuid,
        Study.tenant_id == tenant_id,
    ).first()
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found.")
    return study


@router.get("", response_model=List[StudyResponse])
def list_studies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    return (
        db.query(Study)
        .filter(Study.tenant_id == current_user.tenant_id)
        .order_by(Study.created_at.desc())
        .all()
    )


@router.post("", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
def create_study(
    body: StudyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_validator),
):
    # Enforce uniqueness of study_id within the tenant
    existing = db.query(Study).filter(
        Study.tenant_id == current_user.tenant_id,
        Study.study_id  == body.study_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A study with STUDYID '{body.study_id}' already exists.",
        )

    study = Study(
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
        **body.model_dump(),
    )
    db.add(study)
    db.commit()
    return study


@router.get("/{study_id}", response_model=StudyResponse)
def get_study(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    return _get_study_or_404(study_id, current_user.tenant_id, db)


@router.put("/{study_id}", response_model=StudyResponse)
def update_study(
    study_id: uuid.UUID,
    body: StudyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_validator),
):
    study = _get_study_or_404(study_id, current_user.tenant_id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(study, field, value)
    db.commit()
    return study


@router.delete("/{study_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study(
    study_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    study = _get_study_or_404(study_id, current_user.tenant_id, db)
    study.status = "archived"   # soft-delete
    db.commit()
