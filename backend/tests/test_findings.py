"""
Integration tests for /api/v1/validation/findings/*

Covers:
  - GET   /validation/findings           list with filters
  - GET   /validation/findings/{id}      fetch single finding
  - PATCH /validation/findings/{id}      resolve / waive
  - Tenant isolation
  - RBAC enforcement
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.finding import Finding
from app.models.validation import ValidationJob


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_job(db, tenant, study, user, status="completed") -> ValidationJob:
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


def _make_finding(
    db,
    tenant,
    study,
    job,
    *,
    severity: str = "HIGH",
    domain: str = "DM",
    rule_id: str | None = None,
    status: str = "open",
    usubjid: str | None = "SUBJ-001",
) -> Finding:
    f = Finding(
        tenant_id=tenant.id,
        job_id=job.id,
        study_id=study.id,
        finding_type="SDTM_RULE",
        rule_id=rule_id or f"SDTM_{domain}_001",
        severity=severity,
        domain=domain,
        field="USUBJID",
        message=f"Rule violation in {domain}.",
        row_index=1,
        usubjid=usubjid,
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


# ── GET /validation/findings ──────────────────────────────────────────────────

class TestListFindings:
    def test_empty(self, client, viewer_headers):
        resp = client.get("/api/v1/validation/findings", headers=viewer_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_findings_for_tenant(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        _make_finding(db, tenant, study, job)
        resp = client.get("/api/v1/validation/findings", headers=viewer_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_study_id(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        _make_finding(db, tenant, study, job)
        resp = client.get(
            f"/api/v1/validation/findings?study_id={study.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_job_id(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        _make_finding(db, tenant, study, job)
        resp = client.get(
            f"/api/v1/validation/findings?job_id={job.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_severity(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        _make_finding(db, tenant, study, job, severity="CRIT")
        _make_finding(db, tenant, study, job, severity="LOW")

        resp = client.get(
            "/api/v1/validation/findings?severity=CRIT",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        findings = resp.json()
        assert len(findings) == 1
        assert findings[0]["severity"] == "CRIT"

    def test_filter_by_domain(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        _make_finding(db, tenant, study, job, domain="DM")
        _make_finding(db, tenant, study, job, domain="VS")

        resp = client.get(
            "/api/v1/validation/findings?domain=VS",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        findings = resp.json()
        assert len(findings) == 1
        assert findings[0]["domain"] == "VS"

    def test_filter_by_status(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        _make_finding(db, tenant, study, job, status="open")
        _make_finding(db, tenant, study, job, status="resolved")

        resp = client.get(
            "/api/v1/validation/findings?status=open",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        results = resp.json()
        assert all(f["status"] == "open" for f in results)

    def test_filter_by_usubjid(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        _make_finding(db, tenant, study, job, usubjid="SUBJ-001")
        _make_finding(db, tenant, study, job, usubjid="SUBJ-002")

        resp = client.get(
            "/api/v1/validation/findings?usubjid=SUBJ-001",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["usubjid"] == "SUBJ-001"

    def test_pagination_limit(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        for i in range(5):
            _make_finding(db, tenant, study, job, usubjid=f"SUBJ-{i:03d}")

        resp = client.get(
            "/api/v1/validation/findings?limit=2",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_tenant_isolation(
        self, client, db, viewer_headers
    ):
        """Findings from another tenant must be invisible."""
        from app.models.tenant import Tenant
        from app.models.study import Study

        other_t = Tenant(
            name="Secret CRO",
            slug="secret-cro",
            plan="trial",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_t)
        db.flush()

        other_s = Study(
            tenant_id=other_t.id,
            study_id="SECRET-001",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_s)
        db.flush()

        other_j = ValidationJob(
            tenant_id=other_t.id,
            study_id=other_s.id,
            dataset_ids=[],
            rule_profile="sdtm_default",
            status="completed",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_j)
        db.flush()

        _make_finding(db, other_t, other_s, other_j)
        db.commit()

        resp = client.get("/api/v1/validation/findings", headers=viewer_headers)
        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /validation/findings/{id} ────────────────────────────────────────────

class TestGetFinding:
    def test_get_existing_finding(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job = _make_job(db, tenant, study, admin_user)
        finding = _make_finding(db, tenant, study, job)

        resp = client.get(
            f"/api/v1/validation/findings/{finding.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"]       == str(finding.id)
        assert body["rule_id"]  == finding.rule_id
        assert body["severity"] == finding.severity
        assert body["domain"]   == finding.domain
        assert body["status"]   == "open"

    def test_get_nonexistent_finding_returns_404(self, client, viewer_headers):
        resp = client.get(
            f"/api/v1/validation/findings/{uuid.uuid4()}",
            headers=viewer_headers,
        )
        assert resp.status_code == 404

    def test_cannot_access_other_tenants_finding(
        self, client, db, viewer_headers
    ):
        from app.models.tenant import Tenant
        from app.models.study import Study

        other_t = Tenant(
            name="Hidden CRO",
            slug="hidden-cro",
            plan="trial",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_t)
        db.flush()

        other_s = Study(
            tenant_id=other_t.id,
            study_id="HIDDEN-001",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_s)
        db.flush()

        other_j = ValidationJob(
            tenant_id=other_t.id,
            study_id=other_s.id,
            dataset_ids=[],
            rule_profile="sdtm_default",
            status="completed",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_j)
        db.flush()

        hidden_f = _make_finding(db, other_t, other_s, other_j)

        resp = client.get(
            f"/api/v1/validation/findings/{hidden_f.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 404


# ── PATCH /validation/findings/{id} ──────────────────────────────────────────

class TestResolveFinding:
    def test_validator_can_resolve(
        self, client, db, tenant, study, admin_user, validator_headers, validator_user
    ):
        job     = _make_job(db, tenant, study, admin_user)
        finding = _make_finding(db, tenant, study, job)

        resp = client.patch(
            f"/api/v1/validation/findings/{finding.id}",
            json={"status": "resolved", "resolution_note": "Confirmed as expected."},
            headers=validator_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"]          == "resolved"
        assert body["resolution_note"] == "Confirmed as expected."
        assert body["resolved_by"]     == str(validator_user.id)
        assert body["resolved_at"]     is not None

    def test_validator_can_waive(
        self, client, db, tenant, study, admin_user, validator_headers
    ):
        job     = _make_job(db, tenant, study, admin_user)
        finding = _make_finding(db, tenant, study, job)

        resp = client.patch(
            f"/api/v1/validation/findings/{finding.id}",
            json={"status": "waived", "resolution_note": "Approved deviation."},
            headers=validator_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "waived"

    def test_viewer_cannot_resolve(
        self, client, db, tenant, study, admin_user, viewer_headers
    ):
        job     = _make_job(db, tenant, study, admin_user)
        finding = _make_finding(db, tenant, study, job)

        resp = client.patch(
            f"/api/v1/validation/findings/{finding.id}",
            json={"status": "resolved"},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_resolve_already_resolved_returns_409(
        self, client, db, tenant, study, admin_user, validator_headers
    ):
        job     = _make_job(db, tenant, study, admin_user)
        finding = _make_finding(db, tenant, study, job, status="resolved")

        resp = client.patch(
            f"/api/v1/validation/findings/{finding.id}",
            json={"status": "resolved"},
            headers=validator_headers,
        )
        assert resp.status_code == 409
        assert "resolved" in resp.json()["detail"]

    def test_invalid_status_returns_400(
        self, client, db, tenant, study, admin_user, validator_headers
    ):
        job     = _make_job(db, tenant, study, admin_user)
        finding = _make_finding(db, tenant, study, job)

        resp = client.patch(
            f"/api/v1/validation/findings/{finding.id}",
            json={"status": "bogus"},
            headers=validator_headers,
        )
        assert resp.status_code == 400

    def test_resolve_nonexistent_finding_returns_404(
        self, client, validator_headers
    ):
        resp = client.patch(
            f"/api/v1/validation/findings/{uuid.uuid4()}",
            json={"status": "resolved"},
            headers=validator_headers,
        )
        assert resp.status_code == 404

    def test_db_persists_resolution(
        self, client, db, tenant, study, admin_user, validator_headers
    ):
        """Resolution must actually persist in PostgreSQL, not just in memory."""
        job     = _make_job(db, tenant, study, admin_user)
        finding = _make_finding(db, tenant, study, job)

        client.patch(
            f"/api/v1/validation/findings/{finding.id}",
            json={"status": "resolved", "resolution_note": "Verified."},
            headers=validator_headers,
        )

        db.expire(finding)   # force a fresh SELECT
        db.refresh(finding)
        assert finding.status          == "resolved"
        assert finding.resolution_note == "Verified."
        assert finding.resolved_at     is not None
