"""
/api/v1/ai/*  — Claude-powered AI endpoints.

All endpoints require a valid JWT and at minimum the ROLE_VALIDATOR role
(mapped from the spec's "analyst role minimum").

TODO-AI-005: Add per-tenant rate limiting (e.g. 100 AI calls/hour).
             Implement using a Redis sliding-window counter keyed by
             (tenant_id, endpoint).  Return HTTP 429 with Retry-After header
             when the quota is exceeded.

TODO-AI-006: Record an audit trail entry for every AI call containing:
             user_id, tenant_id, endpoint, model, input_summary,
             output_length, latency_ms, timestamp.  Write to the audit_logs
             table via core/audit.py so it is immutable and queryable.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.rbac import require_admin, require_validator
from app.database import get_db
from app.models.finding import Finding
from app.models.study import Study
from app.models.user import User
from app.models.validation import ValidationJob
from app.services.ai.claude_service import ClaudeServiceError
from app.services.ai import claude_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ReportNarrativeRequest(BaseModel):
    validation_result_id: uuid.UUID


class ReportNarrativeResponse(BaseModel):
    narrative: str


class ExplainAnomalyRequest(BaseModel):
    anomaly_id: uuid.UUID


class ExplainAnomalyResponse(BaseModel):
    explanation: str


class NLQueryRequest(BaseModel):
    question: str
    study_id: uuid.UUID


class NLQueryResponse(BaseModel):
    answer: str


class SuggestRulesRequest(BaseModel):
    study_id: uuid.UUID


class SuggestRulesResponse(BaseModel):
    suggested_profile: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service_error_to_http(exc: ClaudeServiceError) -> HTTPException:
    """Map a ClaudeServiceError to an appropriate HTTP exception."""
    msg = str(exc)
    if "not configured" in msg.lower():
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured on this deployment.",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"AI service error: {msg}",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/report-narrative",
    response_model=ReportNarrativeResponse,
    summary="Generate a plain-English narrative for a validation report",
)
async def generate_report_narrative(
    body: ReportNarrativeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_validator),
):
    """
    Fetch a completed ValidationJob and its findings, then ask Claude to
    produce a narrative summary suitable for a 21 CFR Part 11 PDF report.
    """
    job = db.query(ValidationJob).filter(
        ValidationJob.id == body.validation_result_id,
        ValidationJob.tenant_id == current_user.tenant_id,
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Validation job not found.")
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Validation job is not yet completed (status={job.status!r}).",
        )

    # Build a findings summary (avoid sending raw ORM objects)
    findings = db.query(Finding).filter(Finding.job_id == job.id).all()
    sev_counts = {"CRIT": 0, "HIGH": 0, "MED": 0, "LOW": 0}
    domain_counts: dict[str, int] = {}
    top_findings = []
    for f in findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1
        domain_counts[f.domain] = domain_counts.get(f.domain, 0) + 1
        # Include up to 30 HIGH/CRIT findings in the prompt for context
        if f.severity in ("CRIT", "HIGH") and len(top_findings) < 30:
            top_findings.append({
                "rule_id": f.rule_id,
                "severity": f.severity,
                "domain": f.domain,
                "field": f.field,
                "message": f.message,
                "usubjid": f.usubjid,
            })

    validation_results = {
        "job_id": str(job.id),
        "total": len(findings),
        "domains": domain_counts,
        **sev_counts,
        "representative_findings": top_findings,
    }

    # Fetch study metadata
    study = db.get(Study, job.study_id)
    study_metadata = {
        "study_id": study.study_id if study else str(job.study_id),
        "title": study.title if study else None,
        "phase": study.phase if study else None,
        "sponsor": study.sponsor if study else None,
        "therapeutic_area": study.therapeutic_area if study else None,
    }

    try:
        narrative = await claude_service.generate_report_narrative(
            validation_results=validation_results,
            study_metadata=study_metadata,
        )
    except ClaudeServiceError as exc:
        raise _service_error_to_http(exc) from exc

    return ReportNarrativeResponse(narrative=narrative)


@router.post(
    "/explain-anomaly",
    response_model=ExplainAnomalyResponse,
    summary="Get a clinical explanation for an Isolation Forest anomaly finding",
)
async def explain_anomaly(
    body: ExplainAnomalyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_validator),
):
    """
    Load an ANOMALY-type finding from the DB and ask Claude to explain it
    in clinical terms with recommended data management actions.
    """
    finding = db.query(Finding).filter(
        Finding.id == body.anomaly_id,
        Finding.tenant_id == current_user.tenant_id,
        Finding.finding_type == "ANOMALY",
    ).first()
    if finding is None:
        raise HTTPException(
            status_code=404,
            detail="Anomaly finding not found or not of type ANOMALY.",
        )

    anomaly_dict = {
        "rule_id": finding.rule_id,
        "usubjid": finding.usubjid,
        "field": finding.field,
        "message": finding.message,
        "severity": finding.severity,
        "evidence": finding.evidence,
    }

    try:
        explanation = await claude_service.explain_anomaly(
            anomaly=anomaly_dict,
            domain=finding.domain,
        )
    except ClaudeServiceError as exc:
        raise _service_error_to_http(exc) from exc

    return ExplainAnomalyResponse(explanation=explanation)


@router.post(
    "/query",
    response_model=NLQueryResponse,
    summary="Natural-language query over validation results for a study",
)
async def nl_query(
    body: NLQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_validator),
):
    """
    Answer a free-text question about validation findings for a given study.

    Provides the most recent completed job's summary plus up to 50 findings
    as context.  Questions like "Which subjects are missing AESTDTC?" or
    "How many CRIT findings are in DM?" are handled well.

    TODO-AI-004: Accept a session_id to enable multi-turn conversations.
    """
    # Fetch the most recent completed job for this study + tenant
    job = (
        db.query(ValidationJob)
        .filter(
            ValidationJob.study_id == body.study_id,
            ValidationJob.tenant_id == current_user.tenant_id,
            ValidationJob.status == "completed",
        )
        .order_by(ValidationJob.completed_at.desc())
        .first()
    )
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="No completed validation job found for this study.",
        )

    findings = db.query(Finding).filter(Finding.job_id == job.id).limit(50).all()
    sev_counts = {"CRIT": 0, "HIGH": 0, "MED": 0, "LOW": 0}
    for f in findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1

    context = {
        "job_id": str(job.id),
        "study_id": str(body.study_id),
        "summary": sev_counts,
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "domain": f.domain,
                "field": f.field,
                "message": f.message,
                "usubjid": f.usubjid,
                "status": f.status,
            }
            for f in findings
        ],
    }

    try:
        answer = await claude_service.nl_query(
            question=body.question,
            context=context,
        )
    except ClaudeServiceError as exc:
        raise _service_error_to_http(exc) from exc

    return NLQueryResponse(answer=answer)


@router.post(
    "/suggest-rules",
    response_model=SuggestRulesResponse,
    summary="Suggest a CDISC validation rule profile for a study's dataset",
)
async def suggest_rules(
    body: SuggestRulesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_validator),
):
    """
    Pull a sample of the most recently uploaded dataset for this study and
    ask Claude to recommend an appropriate CDISC validation rule profile.

    Useful during study onboarding when the right profile is uncertain.
    """
    from app.models.dataset import Dataset
    from app.storage.backends import get_storage
    import json as _json

    # Fetch the most recent dataset for this study
    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.study_id == body.study_id,
            Dataset.tenant_id == current_user.tenant_id,
        )
        .order_by(Dataset.created_at.desc())
        .first()
    )
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="No dataset found for this study.",
        )

    # Read up to the first ~10 KB of the file as a sample
    try:
        storage = get_storage()
        raw = storage.read(dataset.storage_uri)
        sample_raw = raw[:10_000]
    except Exception as exc:
        log.warning("Could not read dataset storage for suggest_rules: %s", exc)
        sample_raw = b""

    sample_rows: list[dict] = []
    if sample_raw:
        try:
            parsed = _json.loads(sample_raw.decode("utf-8", errors="replace"))
            if isinstance(parsed, list):
                sample_rows = parsed[:20]
            elif isinstance(parsed, dict):
                # Dataset-JSON rows key
                rows = parsed.get("rows", parsed.get("records", []))
                sample_rows = rows[:20]
        except (_json.JSONDecodeError, UnicodeDecodeError):
            pass  # non-JSON dataset; sample_rows stays empty

    dataset_sample = {
        "domain": dataset.domain,
        "filename": dataset.filename,
        "file_format": dataset.file_format,
        "row_count": dataset.row_count,
        "columns": list(sample_rows[0].keys()) if sample_rows else [],
        "sample_rows": sample_rows[:5],
    }

    try:
        suggested_profile = await claude_service.suggest_rule_profile(
            dataset_sample=dataset_sample,
        )
    except ClaudeServiceError as exc:
        raise _service_error_to_http(exc) from exc

    return SuggestRulesResponse(suggested_profile=suggested_profile)
