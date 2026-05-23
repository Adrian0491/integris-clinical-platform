"""
Integration tests for /api/v1/validation/*

Covers:
  - POST /validation/run           submit a job (Celery dispatch is mocked)
  - GET  /validation/jobs          list jobs
  - GET  /validation/jobs/{id}     fetch a single job
  - GET  /validation/summary/{id}  aggregated findings summary
  - RBAC enforcement
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.dataset import Dataset
from app.models.finding import Finding
from app.models.study import Study
from app.models.tenant import Tenant
from app.models.validation import ValidationJob


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_dataset(db, tenant, study, user) -> Dataset:
    from datetime import datetime, timezone

    ds = Dataset(
        tenant_id=tenant.id,
        study_id=study.id,
        uploaded_by=user.id,
        domain="DM",
        filename="dm.csv",
        storage_uri="file:///tmp/cdtool_test_storage/dm.csv",
        file_format="csv",
        row_count=10,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def _make_job(db, tenant, study, user, status="queued") -> ValidationJob:
    from datetime import datetime, timezone

    job = ValidationJob(
        tenant_id=tenant.id,
        study_id=study.id,
        submitted_by=user.id,
        dataset_ids=[],
        rule_profile="sdtm_default",
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _make_finding(db, tenant, study, job, severity="HIGH", domain="DM") -> Finding:
    from datetime import datetime, timezone

    f = Finding(
        tenant_id=tenant.id,
        job_id=job.id,
        study_id=study.id,
        finding_type="SDTM_RULE",
        rule_id=f"SDTM_{domain}_001",
        severity=severity,
        domain=domain,
        field="USUBJID",
        message="Missing required field USUBJID.",
        row_index=1,
        status="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


# ── POST /validation/run ──────────────────────────────────────────────────────

class TestRunValidation:
    def test_submit_job_returns_202(
        self, client, db, tenant, study, validator_headers, validator_user
    ):
        dataset = _make_dataset(db, tenant, study, validator_user)

        mock_result = MagicMock()
        mock_result.id = str(uuid.uuid4())

        with patch(
            "app.workers.tasks.run_validation_job.apply_async",
            return_value=mock_result,
        ):
            resp = client.post(
                "/api/v1/validation/run",
                json={
                    "study_id":    str(study.id),
                    "dataset_ids": [str(dataset.id)],
                    "rule_profile": "sdtm_default",
                },
                headers=validator_headers,
            )

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"]       == "queued"
        assert body["study_id"]     == str(study.id)
        assert str(dataset.id)      in body["dataset_ids"]
        assert body["celery_task_id"] == mock_result.id

    def test_viewer_cannot_submit_job(
        self, client, db, tenant, study, viewer_headers, viewer_user
    ):
        dataset = _make_dataset(db, tenant, study, viewer_user)

        resp = client.post(
            "/api/v1/validation/run",
            json={
                "study_id":    str(study.id),
                "dataset_ids": [str(dataset.id)],
            },
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_unauthenticated_cannot_submit(self, client, study):
        resp = client.post(
            "/api/v1/validation/run",
            json={"study_id": str(study.id), "dataset_ids": []},
        )
        assert resp.status_code in (401, 403)


# ── GET /validation/jobs ──────────────────────────────────────────────────────

class TestListJobs:
    def test_empty_list(self, client, viewer_headers):
        resp = client.get("/api/v1/validation/jobs", headers=viewer_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_own_tenant_jobs(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        _make_job(db, tenant, study, admin_user)
        resp = client.get("/api/v1/validation/jobs", headers=viewer_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_study_id(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        _make_job(db, tenant, study, admin_user)
        resp = client.get(
            f"/api/v1/validation/jobs?study_id={study.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_study_id_no_match(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        _make_job(db, tenant, study, admin_user)
        resp = client.get(
            f"/api/v1/validation/jobs?study_id={uuid.uuid4()}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /validation/jobs/{id} ─────────────────────────────────────────────────

class TestGetJob:
    def test_get_existing_job(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        resp = client.get(
            f"/api/v1/validation/jobs/{job.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(job.id)

    def test_get_nonexistent_job_returns_404(self, client, viewer_headers):
        resp = client.get(
            f"/api/v1/validation/jobs/{uuid.uuid4()}",
            headers=viewer_headers,
        )
        assert resp.status_code == 404

    def test_cannot_get_other_tenants_job(
        self, client, db, viewer_headers
    ):
        from datetime import datetime, timezone

        other_tenant = Tenant(
            name="Foreign CRO",
            slug="foreign-cro",
            plan="trial",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_tenant)
        db.flush()

        other_study = Study(
            tenant_id=other_tenant.id,
            study_id="FOREIGN-001",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_study)
        db.flush()

        other_job = ValidationJob(
            tenant_id=other_tenant.id,
            study_id=other_study.id,
            dataset_ids=[],
            rule_profile="sdtm_default",
            status="queued",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_job)
        db.commit()

        resp = client.get(
            f"/api/v1/validation/jobs/{other_job.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 404


# ── GET /validation/summary/{id} ──────────────────────────────────────────────

class TestValidationSummary:
    def test_summary_no_findings(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user, status="completed")
        resp = client.get(
            f"/api/v1/validation/summary/{job.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["CRIT"] == 0
        assert body["HIGH"] == 0
        assert body["MED"]  == 0
        assert body["LOW"]  == 0
        assert body["domains"] == {}

    def test_summary_with_findings(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user, status="completed")
        _make_finding(db, tenant, study, job, severity="CRIT", domain="DM")
        _make_finding(db, tenant, study, job, severity="HIGH", domain="VS")
        _make_finding(db, tenant, study, job, severity="HIGH", domain="DM")

        resp = client.get(
            f"/api/v1/validation/summary/{job.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["CRIT"]  == 1
        assert body["HIGH"]  == 2
        assert body["MED"]   == 0
        assert body["domains"]["DM"] == 2
        assert body["domains"]["VS"] == 1

    def test_summary_nonexistent_job_returns_404(self, client, viewer_headers):
        resp = client.get(
            f"/api/v1/validation/summary/{uuid.uuid4()}",
            headers=viewer_headers,
        )
        assert resp.status_code == 404
