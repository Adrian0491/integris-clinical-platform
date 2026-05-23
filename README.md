# Integris Clinical Platform

> **Status: Active Development — v0.8 (targeting v1.0 release Q3 2026)**

A proprietary, cloud-native SaaS platform for clinical data validation and regulatory compliance, built for Contract Research Organizations (CROs) and pharmaceutical sponsors operating under FDA and EMA standards.

Developed and maintained by **George Adrian Pircalaboiu**, Founder & CEO/CTO of **Integris Clinical Services LLC**, San Antonio, Texas.

---

## Overview

The Integris Clinical Platform automates the validation of clinical trial datasets against CDISC/SDTM compliance standards, detects data anomalies in real time, generates FDA-ready compliance reports with electronic signatures, and maintains a complete audit trail in accordance with FDA 21 CFR Part 11 requirements.

It addresses a documented gap in the US clinical research industry: the lack of affordable, modern, cloud-native validation tooling accessible to small and mid-size CROs that cannot afford enterprise platforms like Medidata or Veeva.

---

## Core Features

- **CDISC/SDTM Rule-Based Validation** — automated validation across all major SDTM domains (DM, VS, AE, CM, LB, EG, MH, SV) with systematic rule IDs and severity classification (Critical, High, Medium, Low)
- **Cross-Domain Validation** — detects inconsistencies spanning multiple clinical domains (e.g. adverse event dates preceding subject enrollment)
- **CDISC Dataset-JSON v1.1 Support** — native parsing and validation of the FDA's emerging exchange standard
- **Anomaly Detection** — Isolation Forest-based statistical outlier detection on SDTM numeric variables
- **Real-Time Compliance Dashboard** — live aggregated compliance status across all active studies powered by Elasticsearch
- **Automated PDF Compliance Reports** — structured, FDA-ready reports with electronic signature support
- **FDA 21 CFR Part 11 Audit Trail** — immutable, cryptographically hashed audit log of every action
- **Multi-Tenant Architecture** — complete data isolation per CRO client
- **Role-Based Access Control** — configurable user roles with multi-factor authentication

---

## Technology Stack

### Backend
- **Python 3.12** / **FastAPI** — async REST API with OpenAPI documentation
- **PostgreSQL 16** — multi-tenant relational database (GCP Cloud SQL, private IP, CMEK)
- **Elasticsearch 8** — real-time findings aggregation, full-text search, compliance dashboard queries
- **Redis 7** + **Celery** — async validation job processing queue
- **SQLAlchemy 2.0** + **Alembic** — ORM and database migrations
- **JWT RS256** + **TOTP MFA** — asymmetric-key authentication with RFC 6238 multi-factor
- **bcrypt** (passlib) — password hashing (cost factor 12)
- **pyotp** — TOTP token generation and verification

### Frontend
- **Angular 21** — standalone components, signals, `inject()` pattern, `@if`/`@for` control flow
- **Angular Material 3** — UI component library, clinical blue/teal theme
- **TypeScript 5.9** (strict mode)
- Responsive SPA with server-side proxy to backend API

### Infrastructure (GCP)
- **Cloud Run** — serverless, auto-scaling API and Celery worker containers
- **Cloud SQL** (PostgreSQL 16) — private IP only, `ENCRYPTED_ONLY` SSL, pgAudit, PITR
- **Memorystore** (Redis 7.2) — TLS + AUTH, VPC-internal only
- **Cloud Storage** — CMEK encryption, 7-year retention lifecycle for reports
- **Cloud Armor** — WAF with OWASP CRS rules (SQLi, XSS, LFI, RFI), rate limiting, adaptive DDoS protection
- **Cloud KMS** — Customer-Managed Encryption Keys, 90-day rotation
- **Secret Manager** — encrypted credential storage, zero secrets in config files
- **Artifact Registry** — Docker image registry
- **Cloud Build** — CI/CD with canary deployments (10% → 100% traffic shift)
- **Terraform** — full infrastructure as code across dev / staging / prod environments

### Developer Tooling
- **Docker Compose** — complete local development stack (6 services)
- **Makefile** — one-command developer workflow (`make up`, `make migrate`, `make test`)
- **ruff** — linting and formatting
- **mypy** — static type checking
- **pytest** + **httpx** — 107 integration tests

---

## Architecture

```
Internet
   │
   ▼
Cloud Armor WAF ─────────────────── OWASP CRS, rate limiting, DDoS protection
   │
Global HTTPS Load Balancer ───────── TLS 1.3, RESTRICTED cipher policy, Google-managed SSL
   │
   ├─── Cloud Run (API) ─────────────── FastAPI + gunicorn/uvicorn workers
   │         │
   └─── Cloud Run (Worker) ──────────── Celery validation queue
             │
     ┌───────┴────────┬────────────────┐
     ▼                ▼                ▼
Cloud SQL         Memorystore      Cloud Storage
(PostgreSQL 16)   (Redis 7.2)      (Datasets/Reports)
Private IP        TLS + AUTH       CMEK, versioned
CMEK encrypted    VPC-internal     7-yr retention
     │
Secret Manager ── KMS (CMEK) ── Cloud Logging
```

**Local development stack** (Docker Compose):
```
Angular SPA (localhost:4200)
   │ /api/* proxy
FastAPI API (localhost:8000)
   │
   ├── PostgreSQL 16 (localhost:5432)
   ├── Redis 7 (localhost:6379)
   └── Elasticsearch 8 (localhost:9200)
```

---

## Repository Structure

```
integris/
├── backend/                          # FastAPI backend application
│   ├── app/
│   │   ├── api/v1/                   # Route handlers (one file per resource)
│   │   │   ├── auth.py               # Login, logout, refresh, MFA
│   │   │   ├── studies.py            # Study CRUD and lifecycle
│   │   │   ├── datasets.py           # File upload and metadata
│   │   │   ├── validation.py         # Job submission and status
│   │   │   └── findings.py           # Findings list, resolve, waive
│   │   ├── core/                     # Cross-cutting concerns
│   │   │   ├── audit.py              # SQLAlchemy event listener → audit_log
│   │   │   ├── security.py           # JWT signing, key generation
│   │   │   └── dependencies.py       # FastAPI dependency injection (auth, RBAC)
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── user.py               # User, MFA, refresh tokens
│   │   │   ├── study.py              # Study, site, subject
│   │   │   ├── dataset.py            # Dataset file metadata
│   │   │   ├── validation.py         # ValidationJob
│   │   │   ├── finding.py            # Finding, resolution
│   │   │   ├── report.py             # ComplianceReport
│   │   │   ├── signature.py          # ElectronicSignature (21 CFR Part 11)
│   │   │   ├── audit.py              # AuditLog (append-only)
│   │   │   ├── rule_profile.py       # Custom validation rule sets
│   │   │   └── tenant.py             # Multi-tenant organisation model
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   ├── services/                 # Business logic layer
│   │   └── workers/
│   │       ├── celery_app.py         # Celery application instance
│   │       └── tasks.py              # Validation pipeline task
│   ├── alembic/                      # Database migrations
│   │   └── versions/
│   │       └── 001_initial.py        # Full schema (all tables, indexes, FKs)
│   ├── scripts/
│   │   └── generate_keys.py          # RSA-2048 key pair generation → .env
│   ├── tests/                        # Integration test suite
│   │   ├── conftest.py               # Fixtures, test DB engine, HTTP client
│   │   ├── test_auth.py              # Auth flows, MFA, token refresh (62 tests)
│   │   ├── test_studies.py           # Study CRUD, RBAC, data isolation
│   │   ├── test_datasets.py          # File upload, metadata extraction
│   │   ├── test_validation.py        # Validation engine, Celery tasks
│   │   └── test_findings.py          # Findings, resolve/waive, bulk ops
│   ├── Dockerfile                    # Development container
│   ├── requirements.txt              # Production dependencies
│   └── requirements-dev.txt          # Test and development dependencies
│
├── frontend/                         # Angular 21 application
│   └── src/app/
│       ├── core/
│       │   ├── auth/                 # Guards, interceptors
│       │   └── services/             # ApiService, AuthService, typed resource services
│       └── features/
│           ├── auth/                 # Login, MFA challenge
│           ├── shell/                # Sidenav, breadcrumbs, user menu
│           ├── dashboard/            # Compliance summary widgets
│           ├── studies/              # Study list, create/edit dialog, detail view
│           ├── datasets/             # Upload dialog, status polling
│           ├── validation/
│           │   ├── validation-run/   # Submit validation job
│           │   ├── jobs/             # Job list with status chips
│           │   ├── findings/         # Filterable findings table
│           │   └── resolve-dialog/   # Resolve / waive workflow
│           ├── reports/              # Compliance report list, generate, e-sign
│           └── audit/                # Audit trail with date-range filtering
│
├── infra/
│   ├── terraform/
│   │   ├── modules/                  # 11 reusable Terraform modules
│   │   │   ├── networking/           # VPC, subnet, Cloud NAT, VPC connector
│   │   │   ├── kms/                  # CMEK keys (SQL, Storage, Secrets)
│   │   │   ├── cloud-sql/            # PostgreSQL 16, pgAudit, PITR
│   │   │   ├── memorystore/          # Redis 7.2, TLS, AUTH
│   │   │   ├── storage/              # 3 buckets, lifecycle policies
│   │   │   ├── secrets/              # 8 named secrets, IAM bindings
│   │   │   ├── cloud-armor/          # WAF rules, rate limits
│   │   │   ├── cloud-run/            # API + worker services
│   │   │   ├── load-balancer/        # HTTPS LB, TLS policy, redirect
│   │   │   ├── monitoring/           # Alert policies, uptime checks
│   │   │   └── artifact-registry/    # Docker image repository
│   │   └── environments/
│   │       ├── dev/                  # Scale-to-zero, no CMEK, no Cloud Armor
│   │       ├── staging/              # 1 min instance, CMEK, Cloud Armor
│   │       └── prod/                 # 2 min instances, HA SQL, deletion protection
│   ├── docker/
│   │   ├── backend/Dockerfile.prod   # Multi-stage, non-root, gunicorn
│   │   ├── worker/Dockerfile.prod    # Celery + embedded health server
│   │   └── frontend/
│   │       ├── Dockerfile.prod       # node builder → nginx runtime
│   │       └── nginx.conf            # SPA routing, security headers, gzip
│   └── cloudbuild/
│       ├── cloudbuild-pr.yaml        # PR check: lint → test
│       ├── cloudbuild.yaml           # Main branch: build → push → deploy dev
│       └── cloudbuild-prod.yaml      # Tag deploy: verify → migrate → canary → promote
│
├── docker-compose.yml                # Local development stack (6 services)
├── Makefile                          # Developer workflow shortcuts
├── .env.example                      # Environment variable template
├── INSTALL.md                        # Step-by-step installation guide
├── CONTRIBUTING.md                   # Coding standards, branch strategy, PR process
├── SECURITY.md                       # Vulnerability reporting, security architecture
└── CHANGELOG.md                      # Full version history
```

---

## API Reference

Base URL: `http://localhost:8000/api/v1` (dev) / `https://api.integris-clinical.com/api/v1` (prod)

Interactive docs available at `/docs` in development mode.

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create user account |
| `POST` | `/auth/login` | Obtain access + refresh tokens |
| `POST` | `/auth/refresh` | Rotate access token |
| `POST` | `/auth/logout` | Invalidate refresh token |
| `POST` | `/auth/mfa/enroll` | Generate TOTP secret + QR code |
| `POST` | `/auth/mfa/verify` | Verify TOTP token |

### Studies

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/studies` | List studies (scoped to tenant) |
| `POST` | `/studies` | Create study |
| `GET` | `/studies/{id}` | Study detail |
| `PATCH` | `/studies/{id}` | Update study metadata |
| `DELETE` | `/studies/{id}` | Archive study |

### Datasets

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/studies/{id}/datasets` | List datasets for a study |
| `POST` | `/studies/{id}/datasets` | Upload dataset file (multipart) |
| `GET` | `/datasets/{id}` | Dataset metadata |
| `DELETE` | `/datasets/{id}` | Remove dataset |

### Validation

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/validation/jobs` | Submit validation job |
| `GET` | `/validation/jobs` | List jobs (filter by study, status) |
| `GET` | `/validation/jobs/{id}` | Job detail + progress |

### Findings

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/findings` | List findings (filter by domain, severity, status) |
| `GET` | `/findings/{id}` | Finding detail with evidence |
| `PATCH` | `/findings/{id}/resolve` | Resolve or waive a finding |

### System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness check `{"status":"ok","version":"0.8.0"}` |

---

## Regulatory Alignment

The Integris Clinical Platform directly addresses US federal priorities in clinical data modernization:

- **FDA Dataset-JSON v1.1** — native support for the FDA's emerging electronic study data submission standard (Federal Register, April 2025)
- **NIH Strategic Plan for Data Science 2025–2030** — supports Goal 2 (Enhance Human Derived Data for Research) and Objective 2-2 (Adopt Health IT Standards for Research)
- **CDC Public Health Data Strategy 2025–2026** — real-time, secure clinical data exchange aligned with CDC milestones
- **FDA 21 CFR Part 11** — electronic records and signatures compliance built into the core platform
- **21st Century Cures Act** — modern, interoperable digital health infrastructure

---

## HIPAA Security Controls

| Control | § | Implementation |
|---|---|---|
| Access control | 164.312(a)(1) | RBAC (4 roles), JWT RS256, TOTP MFA |
| Audit controls | 164.312(b) | Immutable `audit_log` table, pgAudit, Cloud Logging |
| Integrity | 164.312(c)(1) | HMAC e-signatures, DB constraints, FK integrity |
| Transmission security | 164.312(e)(1) | TLS 1.3 end-to-end, `RESTRICTED` cipher policy |
| Encryption at rest | 164.312(a)(2)(iv) | Cloud KMS CMEK (staging/prod) |
| Automatic logoff | 164.312(a)(2)(iii) | 30-minute access token TTL |
| Backup and recovery | 164.308(a)(7) | PITR on Cloud SQL; GCS versioning on all buckets |
| Data retention | 164.530(j) | Reports bucket 7-year lifecycle (Nearline → Coldline) |
| Minimum necessary | 164.514(d) | Per-tenant data isolation; scoped IAM service accounts |

---

## Project Status

| Phase | Status | Description |
|---|---|---|
| Phase 0 | ✅ Complete | Prototype stabilization — rule engine, anomaly detection, 62 tests passing |
| Phase 1 | ✅ Complete | FastAPI backend, auth, multi-tenancy, full validation pipeline, 45 integration tests |
| Phase 2 | ✅ Complete | Angular 21 frontend — all 9 modules (dashboard through audit trail) |
| Phase 3 | ✅ Complete | GCP Terraform infrastructure (11 modules), production Dockerfiles, Cloud Build CI/CD |
| Phase 4 | ✅ Complete | Dependency packaging, INSTALL.md, requirements split |
| Phase 5 | ✅ Complete | GitHub presentation — CONTRIBUTING, SECURITY, CHANGELOG, issue/PR templates |
| **v1.0** | 🎯 Target Q3 2026 | Reports/audit API endpoints, production GCP deployment, customer onboarding |

---

## Local Development

### Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Docker Engine | 25.0 | [get.docker.com](https://get.docker.com) |
| Docker Compose | v2.24 | included with Docker Engine |
| Python | 3.12 | [python.org](https://python.org) |
| Node.js | 20 LTS | [nodejs.org](https://nodejs.org) |
| npm | 10 | included with Node.js |

> See [INSTALL.md](INSTALL.md) for the full step-by-step guide with troubleshooting.

### Quick Start (Linux / macOS / WSL)

```bash
# 1. Clone
git clone https://github.com/Adrian0491/integris-clinical-platform.git
cd integris-clinical-platform

# 2. Configure environment
cp .env.example .env
make keys               # generates RSA-2048 JWT key pair → .env
# edit .env to set POSTGRES_PASSWORD and SECRET_KEY

# 3. Start all services (db, redis, elasticsearch, api, worker)
make up                 # waits for images to build, ~2 min first run

# 4. Run database migrations
make migrate            # alembic upgrade head

# 5. Verify
make health             # → {"status": "ok", "version": "0.8.0"}

# 6. Start the Angular dev server (separate terminal)
make frontend           # opens http://localhost:4200
```

### Quick Start (Windows PowerShell)

```powershell
# 1. Clone
git clone https://github.com/Adrian0491/integris-clinical-platform.git
cd integris-clinical-platform

# 2. Configure environment
Copy-Item .env.example .env
python backend\scripts\generate_keys.py   # writes JWT keys to .env
# edit .env to set POSTGRES_PASSWORD and SECRET_KEY

# 3. Start all services
docker compose up -d --build

# 4. Run database migrations
docker compose exec api sh -c "cd /app/backend && alembic upgrade head"

# 5. Verify
curl http://localhost:8000/health

# 6. Start Angular dev server (separate terminal)
cd frontend; npx ng serve --open
```

Navigate to **http://localhost:4200**

---

## Makefile Reference

```bash
make up              # Start all Docker services
make up-infra        # Start only db, redis, elasticsearch (no app containers)
make down            # Stop all services
make clean           # Stop and remove all volumes (DESTROYS LOCAL DATA)
make build           # Rebuild Docker images from scratch
make migrate         # Run Alembic migrations (upgrade head)
make migrate-down    # Downgrade one migration step
make makemigration msg="describe change"  # Autogenerate migration
make keys            # Generate RSA-2048 JWT key pair → .env
make health          # Curl the /health endpoint
make logs            # Tail FastAPI logs
make logs-all        # Tail all service logs
make frontend        # Start Angular dev server with hot reload
make frontend-build  # Production build → frontend/dist/
make test            # Full integration test suite (107 tests)
make test-fast       # Run tests, stop on first failure (-x)
make test-auth       # Auth tests only
make test-validation # Validation pipeline tests only
```

---

## Running Tests

Tests use a real PostgreSQL database (`cdtool_test`). Start the infrastructure first:

```bash
make up-infra        # db + redis only (faster than full stack)

# Install Python dev dependencies if not already installed
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# Run the full suite
make test

# Run with coverage report
cd backend && pytest tests/ --cov=app --cov-report=term-missing
```

**Current test counts:**

| Module | Tests |
|---|---|
| `test_auth.py` | 62 |
| `test_studies.py` | — |
| `test_datasets.py` | — |
| `test_validation.py` | — |
| `test_findings.py` | — |
| **Total** | **107** |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Branch naming conventions
- Conventional Commits format
- Pull request requirements
- Python and Angular coding standards
- Database migration checklist
- Code review guidelines

## Security

To report a vulnerability, **do not open a public issue**. See [SECURITY.md](SECURITY.md) for the private disclosure process and security architecture documentation.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history from v0.1.0 (prototype) to the current release.

---

## About

**Integris Clinical Services LLC**  
San Antonio, Texas, United States

Building modern clinical data infrastructure for the US clinical research industry.

---

*This repository contains proprietary software. © 2026 Integris Clinical Services LLC. All rights reserved.*
