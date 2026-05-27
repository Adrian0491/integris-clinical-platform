"""
/api/v1/validation/*  — submit jobs, poll status, get summaries.
"""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rbac import get_current_user, require_validator, require_viewer
from app.database import get_db
from app.models.finding import Finding
from app.models.user import User
from app.models.validation import ValidationJob
from app.schemas.validation import (
    ValidationJobResponse,
    ValidationRunRequest,
    ValidationSummary,
)

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/run", response_model=ValidationJobResponse, status_code=status.HTTP_202_ACCEPTED)
def run_validation(
    body:         ValidationRunRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_validator),
):
    """
    Submit a validation job and run it synchronously.

    # TODO: ASYNC IMPLEMENTATION REQUIRED BEFORE PRODUCTION LAUNCH
    # ---------------------------------------------------------------
    # This endpoint currently runs validation synchronously (blocking).
    # Once the platform is live with paying clients, this must be
    # converted to use Celery + Redis for async task processing.
    #
    # Required infrastructure:
    #   - GCP Memorystore Redis (Basic M1, ~$36/month)
    #   - Celery worker deployed as a separate Cloud Run service
    #   - REDIS_URL env var set in Cloud Run
    #
    # To re-enable async, restore the original implementation:
    #   result = run_validation_job.apply_async(
    #       args=[str(job.id)],
    #       queue="validation",
    #   )
    #   job.celery_task_id = result.id
    # ---------------------------------------------------------------
    """
    from app.workers.tasks import run_validation_job

    job = ValidationJob(
        tenant_id=current_user.tenant_id,
        study_id=body.study_id,
        submitted_by=current_user.id,
        dataset_ids=[str(did) for did in body.dataset_ids],
        rule_profile=body.rule_profile,
        status="queued",
    )
    db.add(job)
    db.commit()

    # Run synchronously (bypassing Celery for dev — see TODO above)
    run_validation_job(str(job.id))

    db.refresh(job)
    return job


@router.get("/jobs", response_model=List[ValidationJobResponse])
def list_jobs(
    study_id:     uuid.UUID | None = None,
    db:           Session          = Depends(get_db),
    current_user: User             = Depends(require_viewer),
):
    q = db.query(ValidationJob).filter(ValidationJob.tenant_id == current_user.tenant_id)
    if study_id:
        q = q.filter(ValidationJob.study_id == study_id)
    return q.order_by(ValidationJob.created_at.desc()).all()


@router.get("/jobs/{job_id}", response_model=ValidationJobResponse)
def get_job(
    job_id:       uuid.UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_viewer),
):
    job = db.query(ValidationJob).filter(
        ValidationJob.id        == job_id,
        ValidationJob.tenant_id == current_user.tenant_id,
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Validation job not found.")
    return job


@router.get("/summary/{job_id}", response_model=ValidationSummary)
def get_summary(
    job_id:       uuid.UUID,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_viewer),
):
    # Confirm job is accessible
    job = db.query(ValidationJob).filter(
        ValidationJob.id        == job_id,
        ValidationJob.tenant_id == current_user.tenant_id,
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Validation job not found.")

    findings = db.query(Finding).filter(Finding.job_id == job_id).all()

    sev_counts = {sev: 0 for sev in ["CRIT", "HIGH", "MED", "LOW"]}
    domain_counts: dict[str, int] = {}
    for f in findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1
        domain_counts[f.domain] = domain_counts.get(f.domain, 0) + 1

    return ValidationSummary(
        job_id=job_id,
        total=len(findings),
        domains=domain_counts,
        **sev_counts,
    )
