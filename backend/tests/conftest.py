"""
Pytest fixtures for CDTool backend integration tests.

Prerequisites (must be running before the test suite):
  - PostgreSQL on localhost:5432  (databases: cdtool  +  cdtool_test)
    Easiest: `docker compose up -d db db-init`

Run from the backend/ directory:
    PYTHONPATH=..:. pytest tests/ -v

All application behaviour is exercised against a *real* PostgreSQL database;
no mocking of SQL queries.  Celery task dispatch is patched so no worker needs
to be running.
"""
from __future__ import annotations

import os
import uuid

# ── Must happen BEFORE any `from app import ...` so Settings / engine are
# ── created with the test database URL, not the production one.
#
# Honour an explicit TEST_DATABASE_URL if provided (e.g. in CI), otherwise
# fall back to localhost.  Always override DATABASE_URL so the test engine
# never touches the production database.
_TEST_DB_URL_DEFAULT = "postgresql://cdtool:cdtool_dev@localhost:5432/cdtool_test"
os.environ["DATABASE_URL"]       = os.environ.get("TEST_DATABASE_URL", _TEST_DB_URL_DEFAULT)
os.environ["TEST_DATABASE_URL"]  = os.environ["DATABASE_URL"]
os.environ["ENABLE_ES_INDEXING"] = "False"   # never write to ES in tests
os.environ["STORAGE_BACKEND"]    = "local"
os.environ["STORAGE_LOCAL_PATH"] = "/tmp/cdtool_test_storage"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ── App imports (after env-var setup) ────────────────────────────────────────
from app.config import get_settings

get_settings.cache_clear()   # force re-read so Settings() uses the test URL

from app.database import get_db
from app.main import app
from app.models import Base
from app.models.tenant import Tenant
from app.models.user import (
    ROLE_TENANT_ADMIN,
    ROLE_VALIDATOR,
    ROLE_VIEWER,
    User,
)
from app.models.study import Study
from app.core.security import hash_password

_TEST_DB_URL: str = os.environ["DATABASE_URL"]


# ── Session-scoped engine / table creation ────────────────────────────────────

@pytest.fixture(scope="session")
def test_engine():
    """
    Create a SQLAlchemy engine bound to cdtool_test and create all ORM tables.
    Tables are dropped at the end of the test session.
    """
    engine = create_engine(_TEST_DB_URL, echo=False)

    # Fail fast with a helpful message if PostgreSQL is not reachable
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(
            f"PostgreSQL not reachable at {_TEST_DB_URL!r}.\n"
            "Start the stack first:  docker compose up -d db db-init\n"
            f"Original error: {exc}"
        )

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def TestSessionFactory(test_engine):
    """Session-scoped sessionmaker bound to the test engine."""
    return sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


# ── Also point app.database.SessionLocal at the test DB ──────────────────────
# The audit-log after_commit listener creates its own sessions via
# `from app.database import SessionLocal`.  Patching it here ensures audit
# writes stay in cdtool_test and never touch the production database.

@pytest.fixture(scope="session", autouse=True)
def _patch_sessionlocal(TestSessionFactory):
    import app.database as _db_module
    original = _db_module.SessionLocal
    _db_module.SessionLocal = TestSessionFactory
    yield
    _db_module.SessionLocal = original


# ── Per-test table cleanup ────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_tables(test_engine):
    """Truncate every table after each test to guarantee full isolation."""
    yield  # run the test first
    with test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(
                text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE")
            )
        conn.commit()


# ── Per-test DB session ───────────────────────────────────────────────────────

@pytest.fixture()
def db(TestSessionFactory):
    """Provide a fresh SQLAlchemy session; close it after each test."""
    session = TestSessionFactory()
    try:
        yield session
    finally:
        session.close()


# ── FastAPI TestClient with overridden get_db ─────────────────────────────────

@pytest.fixture()
def client(db):
    """
    Return an HTTPX TestClient whose get_db dependency is wired to
    the per-test session so every request shares the same connection.
    """

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ── Common data fixtures ──────────────────────────────────────────────────────

@pytest.fixture()
def tenant(db) -> Tenant:
    """Seed a test tenant."""
    from datetime import datetime, timezone

    t = Tenant(
        name="Acme CRO",
        slug="acme-cro",
        plan="professional",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _make_user(db, tenant: Tenant, email: str, role: str) -> User:
    from datetime import datetime, timezone

    u = User(
        tenant_id=tenant.id,
        email=email,
        full_name=f"Test {role.title()}",
        hashed_password=hash_password("Password123!"),
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def admin_user(db, tenant) -> User:
    return _make_user(db, tenant, "admin@acme.com", ROLE_TENANT_ADMIN)


@pytest.fixture()
def validator_user(db, tenant) -> User:
    return _make_user(db, tenant, "validator@acme.com", ROLE_VALIDATOR)


@pytest.fixture()
def viewer_user(db, tenant) -> User:
    return _make_user(db, tenant, "viewer@acme.com", ROLE_VIEWER)


# ── Auth-header helpers ───────────────────────────────────────────────────────

def _login(client: TestClient, email: str, password: str = "Password123!") -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client, admin_user) -> dict:
    return _login(client, admin_user.email)


@pytest.fixture()
def validator_headers(client, validator_user) -> dict:
    return _login(client, validator_user.email)


@pytest.fixture()
def viewer_headers(client, viewer_user) -> dict:
    return _login(client, viewer_user.email)


# ── Study fixture ─────────────────────────────────────────────────────────────

@pytest.fixture()
def study(db, tenant, admin_user) -> Study:
    from datetime import datetime, timezone

    s = Study(
        tenant_id=tenant.id,
        created_by=admin_user.id,
        study_id="CDTOOL-001",
        title="Phase II Hypertension Study",
        phase="II",
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s
