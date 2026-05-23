"""
Integration tests for /api/v1/auth/*

Covers:
  - POST /login  (success, wrong password, inactive account, nonexistent user)
  - POST /refresh
  - GET  /health  (smoke-test that the app starts up)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.models.user import User


# ── /health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body


# ── POST /api/v1/auth/login ────────────────────────────────────────────────────

class TestLogin:
    def test_login_success_returns_tokens(self, client, admin_user):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "Password123!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self, client, admin_user):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "WrongPassword!"},
        )
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    def test_login_nonexistent_user_returns_401(self, client, tenant):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@acme.com", "password": "Password123!"},
        )
        assert resp.status_code == 401

    def test_login_case_insensitive_email(self, client, admin_user):
        """Email lookup must be case-insensitive."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email.upper(), "password": "Password123!"},
        )
        assert resp.status_code == 200

    def test_login_inactive_user_returns_401(self, client, db, tenant):
        """Deactivated accounts must be rejected."""
        from datetime import datetime, timezone
        from app.core.security import hash_password
        from app.models.user import ROLE_VIEWER

        inactive = User(
            tenant_id=tenant.id,
            email="inactive@acme.com",
            hashed_password=hash_password("Password123!"),
            role=ROLE_VIEWER,
            is_active=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(inactive)
        db.commit()

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@acme.com", "password": "Password123!"},
        )
        assert resp.status_code == 401
        assert "inactive" in resp.json()["detail"].lower()

    def test_login_updates_last_login_at(self, client, db, admin_user):
        assert admin_user.last_login_at is None
        client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "Password123!"},
        )
        db.refresh(admin_user)
        assert admin_user.last_login_at is not None


# ── POST /api/v1/auth/refresh ─────────────────────────────────────────────────

class TestRefresh:
    def test_refresh_returns_new_access_token(self, client, admin_user):
        # First login to get a refresh token
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "Password123!"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # Exchange it for a new access token
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_refresh_invalid_token_returns_401(self, client):
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not.a.valid.token"},
        )
        assert resp.status_code == 401

    def test_refresh_with_access_token_rejected(self, client, admin_user):
        """Passing an access token as a refresh token must be rejected."""
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "Password123!"},
        )
        access_token = login_resp.json()["access_token"]

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert resp.status_code == 401


# ── Protected endpoint requires auth ─────────────────────────────────────────

class TestAuthRequired:
    def test_unauthenticated_request_returns_403(self, client):
        """No Bearer token → FastAPI HTTPBearer returns 403."""
        resp = client.get("/api/v1/studies")
        assert resp.status_code in (401, 403)

    def test_malformed_token_returns_401(self, client):
        resp = client.get(
            "/api/v1/studies",
            headers={"Authorization": "Bearer this.is.garbage"},
        )
        assert resp.status_code == 401
