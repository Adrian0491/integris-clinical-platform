"""
/api/v1/edc/*  — EDC connector endpoints.

Provides connect, study listing, dataset import, and connection-status
operations for all supported EDC systems (Medidata Rave, REDCap, Veeva Vault).

All endpoints require JWT auth and at minimum ROLE_TENANT_ADMIN (admin).

In-memory credential store
--------------------------
EDC connection configs are held in a module-level dict keyed by tenant_id.
This is intentionally temporary — see TODO-EDC-018 for the persistent,
encrypted-at-rest replacement.

TODO-EDC-018: Replace the in-memory _connections store with a persistent
              EDCConnection database table.  Encrypt api_key/username/password
              fields at rest using GCP Cloud KMS via a DEK/KEK envelope:
                from google.cloud import kms
              Store only the ciphertext; decrypt on read inside the request
              handler using the tenant's KMS key ring.

TODO-EDC-019: Add a Celery task ``sync_edc_datasets`` for scheduled background
              data sync.  Configurable per tenant: cron expression stored in the
              EDCConnection row.  On execution:
                1. Restore connector from DB, decrypt credentials.
                2. authenticate()
                3. For each domain in list_domains(): pull_dataset() + import.
                4. Trigger run_validation_job for the new datasets.

TODO-EDC-020: Record an audit trail entry for every EDC connection event:
              who connected, which system, when, and the outcome (success/fail).
              Write to audit_logs via core/audit.py so the log is immutable.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.rbac import require_admin
from app.database import get_db
from app.models.user import User
from app.services.edc.base import EDCConnectionConfig, EDCSystemType
from app.services.edc.factory import EDCConnectorFactory

log = logging.getLogger(__name__)

router = APIRouter(prefix="/edc", tags=["edc"])


# ---------------------------------------------------------------------------
# In-memory connection store (per-tenant)
# TODO-EDC-018: Replace with encrypted DB rows + GCP KMS.
# ---------------------------------------------------------------------------

# Key: tenant_id (str), Value: EDCConnectionConfig
_connections: dict[str, EDCConnectionConfig] = {}

# Connection status log: Key: tenant_id, Value: dict with status + timestamp
_status_log: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class EDCConnectionRequest(BaseModel):
    """Maps directly to EDCConnectionConfig but expressed as a Pydantic model."""
    system_type: EDCSystemType
    base_url:    str
    api_key:     str = ""
    username:    str = ""
    password:    str = ""
    extra:       dict[str, Any] = {}


class EDCConnectResponse(BaseModel):
    status:      str
    system_type: str
    base_url:    str
    message:     str


class StudyListResponse(BaseModel):
    studies: list[dict[str, Any]]
    count:   int


class ImportResponse(BaseModel):
    study_id:      str
    domains:       list[str]
    datasets_created: int
    validation_job_id: str | None
    message:       str


class EDCStatusResponse(BaseModel):
    connected:    bool
    system_type:  str | None
    base_url:     str | None
    last_checked: str | None
    message:      str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_config(tenant_id: str) -> EDCConnectionConfig:
    """Return the stored config for a tenant, or raise 404."""
    cfg = _connections.get(str(tenant_id))
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No EDC connection configured for this tenant.  "
                   "Call POST /api/v1/edc/connect first.",
        )
    return cfg


def _record_status(tenant_id: str, connected: bool, message: str) -> None:
    """Update the in-memory status log for a tenant."""
    _status_log[str(tenant_id)] = {
        "connected":    connected,
        "last_checked": datetime.now(timezone.utc).isoformat(),
        "message":      message,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/connect",
    response_model=EDCConnectResponse,
    summary="Configure and test an EDC connection for this tenant",
)
async def connect(
    body:         EDCConnectionRequest,
    current_user: User    = Depends(require_admin),
):
    """
    Validate an EDC connection by authenticating against the remote system,
    then store the credentials for subsequent API calls.

    The connection is stored in memory per-tenant (one active connection per
    tenant at a time).

    TODO-EDC-018: Encrypt and persist credentials to DB via GCP KMS.
    TODO-EDC-020: Emit an audit log entry for this connect event.
    """
    config = EDCConnectionConfig(
        system_type=body.system_type,
        base_url=body.base_url,
        api_key=body.api_key,
        username=body.username,
        password=body.password,
        tenant_id=str(current_user.tenant_id),
        extra=body.extra,
    )

    try:
        connector = EDCConnectorFactory.create(config)
        await connector.authenticate()
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        _record_status(str(current_user.tenant_id), False, str(exc))
        log.error(
            "EDC connection failed for tenant %s (%s): %s",
            current_user.tenant_id, body.system_type, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"EDC authentication failed: {exc}",
        ) from exc

    # Store the verified config
    _connections[str(current_user.tenant_id)] = config
    _record_status(
        str(current_user.tenant_id),
        True,
        f"Connected to {body.system_type.value} at {body.base_url}",
    )
    log.info(
        "EDC connection stored for tenant %s: %s @ %s",
        current_user.tenant_id, body.system_type, body.base_url,
    )

    return EDCConnectResponse(
        status="connected",
        system_type=body.system_type.value,
        base_url=body.base_url,
        message=f"Successfully authenticated with {body.system_type.value}.",
    )


@router.get(
    "/studies",
    response_model=StudyListResponse,
    summary="List studies available in the connected EDC system",
)
async def list_studies(
    current_user: User = Depends(require_admin),
):
    """
    Retrieve the list of studies/projects from the tenant's connected EDC system.
    """
    config = _get_config(str(current_user.tenant_id))

    try:
        connector = EDCConnectorFactory.create(config)
        await connector.authenticate()
        studies = await connector.list_studies()
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except Exception as exc:
        log.error("EDC list_studies failed for tenant %s: %s", current_user.tenant_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"EDC list_studies failed: {exc}",
        )

    return StudyListResponse(studies=studies, count=len(studies))


@router.post(
    "/import/{study_id}",
    response_model=ImportResponse,
    summary="Import datasets from EDC and trigger CDISC validation",
)
async def import_study(
    study_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_admin),
):
    """
    Pull all available datasets for ``study_id`` from the connected EDC system,
    store them in the platform database, and enqueue a CDISC validation job.

    Steps:
    1. Retrieve the stored EDC connection config for this tenant.
    2. Authenticate and list available SDTM domains.
    3. Pull each domain as Dataset-JSON v1.1 and persist to storage.
    4. Create Dataset records in the platform DB.
    5. Enqueue a ``run_validation_job`` Celery task for all imported datasets.

    TODO-EDC-019: Move steps 2-5 into a Celery task for large studies.
    TODO-EDC-020: Emit an audit log entry for this import event.
    """
    from app.models.dataset import Dataset
    from app.models.study import Study
    from app.models.validation import ValidationJob
    from app.storage.backends import get_storage
    import json as _json

    config = _get_config(str(current_user.tenant_id))

    # ── Resolve platform Study row ────────────────────────────────────────
    # Try to find a study with matching study_id string in this tenant.
    platform_study = (
        db.query(Study)
        .filter(
            Study.study_id == study_id,
            Study.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if platform_study is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Study with study_id={study_id!r} not found in this tenant's "
                "platform.  Create the study first via POST /api/v1/studies."
            ),
        )

    # ── Authenticate + list domains ───────────────────────────────────────
    try:
        connector = EDCConnectorFactory.create(config)
        await connector.authenticate()
        domains = await connector.list_domains(study_id)
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except Exception as exc:
        log.error("EDC import failed (auth/domains) for tenant %s: %s",
                  current_user.tenant_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"EDC connection error: {exc}",
        )

    # ── Pull each domain, persist to storage, create Dataset row ─────────
    storage = get_storage()
    created_datasets: list[Dataset] = []

    for domain in domains:
        try:
            dataset_json = await connector.pull_dataset(study_id, domain)
        except NotImplementedError as exc:
            log.warning("pull_dataset not implemented for domain %s: %s", domain, exc)
            continue
        except Exception as exc:
            log.error("EDC pull_dataset failed for domain %s: %s", domain, exc)
            continue

        # Persist the Dataset-JSON file to storage
        raw_bytes = _json.dumps(dataset_json).encode("utf-8")
        filename  = f"edc_import_{study_id}_{domain}.json"
        uri       = f"edc/{current_user.tenant_id}/{study_id}/{filename}"
        storage.write(uri, raw_bytes)

        ds = Dataset(
            tenant_id=current_user.tenant_id,
            study_id=platform_study.id,
            uploaded_by=current_user.id,
            domain=domain.upper(),
            filename=filename,
            storage_uri=uri,
            file_format="dataset-json",
            row_count=dataset_json.get("records", 0),
        )
        db.add(ds)
        created_datasets.append(ds)

    if not created_datasets:
        return ImportResponse(
            study_id=study_id,
            domains=domains,
            datasets_created=0,
            validation_job_id=None,
            message="No datasets could be imported (all domains stubbed or empty).",
        )

    db.commit()

    # ── Enqueue validation job ────────────────────────────────────────────
    from app.workers.tasks import run_validation_job

    job = ValidationJob(
        tenant_id=current_user.tenant_id,
        study_id=platform_study.id,
        submitted_by=current_user.id,
        dataset_ids=[str(ds.id) for ds in created_datasets],
        rule_profile="sdtm_default",
        status="queued",
    )
    db.add(job)
    db.commit()

    celery_result = run_validation_job.apply_async(
        args=[str(job.id)],
        queue="validation",
    )
    job.celery_task_id = celery_result.id
    db.commit()

    log.info(
        "EDC import complete for tenant=%s study=%s: %d datasets, job=%s",
        current_user.tenant_id, study_id, len(created_datasets), job.id,
    )

    return ImportResponse(
        study_id=study_id,
        domains=domains,
        datasets_created=len(created_datasets),
        validation_job_id=str(job.id),
        message=(
            f"Imported {len(created_datasets)} dataset(s) for study {study_id!r}.  "
            f"Validation job {job.id} queued."
        ),
    )


@router.get(
    "/status",
    response_model=EDCStatusResponse,
    summary="Return the EDC connection status for the current tenant",
)
async def get_status(
    current_user: User = Depends(require_admin),
):
    """
    Return whether this tenant has an active EDC connection, and its details.
    """
    tenant_str = str(current_user.tenant_id)
    cfg        = _connections.get(tenant_str)
    log_entry  = _status_log.get(tenant_str)

    if cfg is None:
        return EDCStatusResponse(
            connected=False,
            system_type=None,
            base_url=None,
            last_checked=None,
            message="No EDC connection configured for this tenant.",
        )

    return EDCStatusResponse(
        connected=log_entry.get("connected", False) if log_entry else False,
        system_type=cfg.system_type.value,
        base_url=cfg.base_url,
        last_checked=log_entry.get("last_checked") if log_entry else None,
        message=log_entry.get("message", "Connection stored.") if log_entry else "Connection stored.",
    )
