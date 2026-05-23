"""
Integration tests for /api/v1/studies/*

Covers:
  - GET    /studies           list (tenant-scoped)
  - POST   /studies           create (validator+)
  - GET    /studies/{id}      fetch
  - PUT    /studies/{id}      update (validator+)
  - DELETE /studies/{id}      soft-delete / archive (admin+)
  - RBAC enforcement (viewer cannot create/delete)
  - Tenant isolation (users cannot see another tenant's studies)
"""
from __future__ import annotations

import uuid

import pytest

from app.models.study import Study
from app.models.tenant import Tenant
from app.models.user import User, ROLE_TENANT_ADMIN, ROLE_VIEWER


# ── Helpers ───────────────────────────────────────────────────────────────────

_STUDY_PAYLOAD = {
    "study_id":         "CDTOOL-TEST-001",
    "title":            "Integration Test Study",
    "phase":            "II",
    "therapeutic_area": "Cardiology",
    "sponsor":          "Acme Pharma",
}


# ── GET /studies ───────────────────────────────────────────────────────────────

class TestListStudies:
    def test_empty_list(self, client, viewer_headers):
        resp = client.get("/api/v1/studies", headers=viewer_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_own_tenant_studies(self, client, viewer_headers, study):
        resp = client.get("/api/v1/studies", headers=viewer_headers)
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()]
        assert str(study.id) in ids

    def test_tenant_isolation(self, client, db, viewer_headers, viewer_user):
        """Studies from another tenant must not appear."""
        from datetime import datetime, timezone
        from app.core.security import hash_password

        other_tenant = Tenant(
            name="Other CRO",
            slug="other-cro",
            plan="trial",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_tenant)
        db.flush()

        other_study = Study(
            tenant_id=other_tenant.id,
            study_id="OTHER-001",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_study)
        db.commit()

        resp = client.get("/api/v1/studies", headers=viewer_headers)
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()]
        assert str(other_study.id) not in ids

    def test_unauthenticated_returns_403(self, client):
        resp = client.get("/api/v1/studies")
        assert resp.status_code in (401, 403)


# ── POST /studies ─────────────────────────────────────────────────────────────

class TestCreateStudy:
    def test_validator_can_create(self, client, validator_headers):
        resp = client.post(
            "/api/v1/studies",
            json=_STUDY_PAYLOAD,
            headers=validator_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["study_id"] == _STUDY_PAYLOAD["study_id"]
        assert body["title"]    == _STUDY_PAYLOAD["title"]
        assert body["phase"]    == _STUDY_PAYLOAD["phase"]
        assert body["status"]   == "active"
        assert "id" in body

    def test_admin_can_create(self, client, admin_headers):
        resp = client.post(
            "/api/v1/studies",
            json=_STUDY_PAYLOAD,
            headers=admin_headers,
        )
        assert resp.status_code == 201

    def test_viewer_cannot_create(self, client, viewer_headers):
        resp = client.post(
            "/api/v1/studies",
            json=_STUDY_PAYLOAD,
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_duplicate_study_id_returns_409(self, client, validator_headers):
        client.post("/api/v1/studies", json=_STUDY_PAYLOAD, headers=validator_headers)
        resp = client.post(
            "/api/v1/studies", json=_STUDY_PAYLOAD, headers=validator_headers
        )
        assert resp.status_code == 409
        assert _STUDY_PAYLOAD["study_id"] in resp.json()["detail"]


# ── GET /studies/{id} ─────────────────────────────────────────────────────────

class TestGetStudy:
    def test_get_existing_study(self, client, viewer_headers, study):
        resp = client.get(f"/api/v1/studies/{study.id}", headers=viewer_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == str(study.id)

    def test_get_nonexistent_study_returns_404(self, client, viewer_headers):
        resp = client.get(
            f"/api/v1/studies/{uuid.uuid4()}",
            headers=viewer_headers,
        )
        assert resp.status_code == 404

    def test_cannot_access_other_tenants_study(self, client, db, viewer_headers):
        from datetime import datetime, timezone

        other_tenant = Tenant(
            name="Another CRO",
            slug="another-cro",
            plan="trial",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_tenant)
        db.flush()

        foreign_study = Study(
            tenant_id=other_tenant.id,
            study_id="FOREIGN-001",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(foreign_study)
        db.commit()

        resp = client.get(
            f"/api/v1/studies/{foreign_study.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 404


# ── PUT /studies/{id} ─────────────────────────────────────────────────────────

class TestUpdateStudy:
    def test_validator_can_update_title(self, client, validator_headers, study):
        resp = client.put(
            f"/api/v1/studies/{study.id}",
            json={"title": "Updated Title"},
            headers=validator_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_viewer_cannot_update(self, client, viewer_headers, study):
        resp = client.put(
            f"/api/v1/studies/{study.id}",
            json={"title": "Viewer Attempt"},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_update_nonexistent_study_returns_404(self, client, validator_headers):
        resp = client.put(
            f"/api/v1/studies/{uuid.uuid4()}",
            json={"title": "Ghost"},
            headers=validator_headers,
        )
        assert resp.status_code == 404


# ── DELETE /studies/{id} ──────────────────────────────────────────────────────

class TestDeleteStudy:
    def test_admin_soft_deletes_study(self, client, db, admin_headers, study):
        resp = client.delete(
            f"/api/v1/studies/{study.id}",
            headers=admin_headers,
        )
        assert resp.status_code == 204

        db.refresh(study)
        assert study.status == "archived"

    def test_validator_cannot_delete(self, client, validator_headers, study):
        resp = client.delete(
            f"/api/v1/studies/{study.id}",
            headers=validator_headers,
        )
        assert resp.status_code == 403

    def test_viewer_cannot_delete(self, client, viewer_headers, study):
        resp = client.delete(
            f"/api/v1/studies/{study.id}",
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_delete_nonexistent_study_returns_404(self, client, admin_headers):
        resp = client.delete(
            f"/api/v1/studies/{uuid.uuid4()}",
            headers=admin_headers,
        )
        assert resp.status_code == 404
