# Changelog — Integris Clinical Platform

All notable changes to the Integris Clinical Platform are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.8.0] — 2026-05-23

**Phase 4: Production Hardening & Developer Experience**

### Added
- `INSTALL.md` — step-by-step installation guide covering prerequisites, Docker Compose setup, migrations, test suite, and troubleshooting for a fresh Linux machine
- `backend/requirements-dev.txt` — separated development dependencies (`pytest`, `ruff`, `mypy`, `httpx`, `factory-boy`, `faker`) from production requirements
- `CONTRIBUTING.md` — coding standards, branch naming, Conventional Commits format, PR process, testing requirements, migration checklist
- `SECURITY.md` — vulnerability reporting process, security architecture documentation, HIPAA control mapping
- `CHANGELOG.md` — full version history
- `.github/ISSUE_TEMPLATE/` — bug report and feature request templates with structured fields
- `.github/PULL_REQUEST_TEMPLATE.md` — standardized PR checklist

### Changed
- `backend/requirements.txt` — removed test-only dependencies (`pytest`, `httpx`), removed redundant standalone `bcrypt` (covered by `passlib[bcrypt]`), added version upper bounds to all packages
- `frontend/package.json` — removed duplicate `@angular/material` from `devDependencies`, updated `packageManager` to `npm@11.8.0`, added `build:prod` and `lint` scripts
- `backend/app/config.py` — updated `APP_NAME` to `"Integris Clinical Platform API"`, bumped `APP_VERSION` to `"0.8.0"`
- `README.md` — complete rewrite from prototype description to production product documentation
- `.gitignore` — replaced broad `*.csv` / `*.json` patterns (which broke `package.json` and `angular.json`) with specific `storage/` and `mock_data/` directory exclusions

---

## [0.7.0] — 2026-04-28

**Phase 3: GCP Deployment Infrastructure**

### Added
- **Terraform modules** (11 modules, 53 files total):
  - `networking` — VPC, subnet, Cloud NAT, Serverless VPC connector
  - `kms` — CMEK keys for Cloud SQL, Cloud Storage, and Secret Manager (90-day rotation)
  - `cloud-sql` — PostgreSQL 16, private IP, `ENCRYPTED_ONLY` SSL, pgAudit, PITR, slow query logging
  - `memorystore` — Redis 7.2, TLS (`SERVER_AUTHENTICATION`), AUTH token, `rediss://` scheme
  - `storage` — 3 buckets (datasets, reports, backups), CMEK, 7-year retention lifecycle for reports
  - `secrets` — 8 named secrets, `ignore_changes` on secret data, Cloud Run SA `secretAccessor` binding
  - `cloud-armor` — OWASP CRS (SQLi, XSS, LFI, RFI), rate limit 1000/min global, 20/min on auth endpoints
  - `cloud-run` — API service (public), worker service (internal), Secret Manager secret injection
  - `load-balancer` — Serverless NEG, TLS 1.3 `RESTRICTED` policy, HTTP→HTTPS redirect
  - `monitoring` — 7 alert policies, uptime check, failed-login log metric
  - `artifact-registry` — Docker image repository
- **Three environments**: `dev`, `staging`, `prod` — environment-specific tier sizing, HA settings, CMEK, and deletion protection
- **Production Dockerfiles**: multi-stage builds (builder → runtime), non-root users (uid 1001), `gunicorn` with `uvicorn` workers
- **Worker Dockerfile**: embedded Python HTTP health server for Cloud Run port requirement, Celery as PID 1
- **Frontend Dockerfile**: `node:22-alpine` builder → `nginx:1.27-alpine` runtime, `dist/frontend/browser` served as static files
- **nginx.conf**: security headers (CSP, HSTS, X-Frame-Options), gzip, SPA `try_files`, 1-year immutable cache for hashed assets, `/health` JSON endpoint
- **Cloud Build pipelines**:
  - `cloudbuild-pr.yaml` — parallel lint + frontend build, then integration tests
  - `cloudbuild.yaml` — build 3 images → push → migrate → deploy dev
  - `cloudbuild-prod.yaml` — verify images → migrate → 10% canary → 60s wait → 100% promote → deploy worker + frontend
- `infra/README.md` — GCP architecture diagram, first-time bootstrap guide, CI/CD trigger table, environment comparison, HIPAA control mapping, Day-2 operations runbook

### Changed
- `backend/requirements.txt` — added `gunicorn>=22.0.0,<24.0.0` for production process management

---

## [0.6.0] — 2026-04-07

**Phase 2 (continued): Reports & Audit Trail Frontend Modules**

### Added
- **Reports module** (`frontend/src/app/features/reports/`):
  - Reports list with status chips (`pending`, `generating`, `completed`, `failed`)
  - Download button (authenticated URL to `/api/v1/reports/{id}/download`)
  - E-signature button — confirm dialog → `POST /api/v1/reports/{id}/sign`
  - `GenerateReportDialogComponent` — select job + report type, trigger generation
  - `ReportsService` — `list()`, `generate()`, `sign()`, `getDownloadUrl()`
- **Audit Trail module** (`frontend/src/app/features/audit/`):
  - Filterable log table: action, user ID, from/to date range (Material datepicker)
  - Color-coded action badges (warn: destructive actions, success: creates/resolves)
  - Tabular-nums timestamp column, truncated user ID with full-text tooltip
  - Server-side pagination with `pageSize` / `pageIndex` / `offset` signals
- `provideNativeDateAdapter()` added to `app.config.ts` — required for `MatDatepicker`

### Fixed
- Removed `MatNativeDateModule` from individual component imports (adapter must be global)

---

## [0.5.0] — 2026-03-24

**Phase 2 (continued): Findings Explorer & Resolve/Waive Workflow**

### Added
- **Findings explorer** (`frontend/src/app/features/validation/findings/`):
  - Multi-column filter bar: domain, severity, status, subject ID
  - Material table with severity badge + icon, rule ID in monospace, status chip, resolve button
  - Server-side pagination
- **Resolve/Waive dialog** (`frontend/src/app/features/validation/resolve-dialog/`):
  - Finding summary card: severity chip, rule code, domain badge, message, evidence block
  - Radio group: `resolved` (green) vs `waived` (grey)
  - 1000-character resolution note textarea with live character counter
  - `saving = signal(false)` spinner state
  - Calls `PATCH /api/v1/findings/{id}/resolve`
- **Developer workflow** scripts:
  - `Makefile` — `make frontend`, `make frontend-build`, `make test-fast`, `make test-auth`, `make keys`
  - `scripts/run.ps1` — Windows PowerShell equivalents for all Makefile targets

---

## [0.4.0] — 2026-03-10

**Phase 2: Angular Frontend Foundation**

### Added
- Angular 21 project scaffold — standalone components, signals, `inject()` pattern, `@if`/`@for` control flow
- Angular Material 3 theme — clinical blue/teal palette, dark/light mode support
- **Authentication** (`frontend/src/app/core/`):
  - Login component with MFA TOTP prompt
  - `AuthService` — login, logout, refresh token via `HttpClient`
  - `AuthInterceptor` — JWT bearer token injection, 401 → refresh → retry
  - `AuthGuard` — route protection for authenticated sections
  - `RoleGuard` — role-based route protection
- **Shell layout**: sidenav with role-filtered navigation, breadcrumbs, user menu
- **Studies module**: list, create dialog, archive action
- **Datasets module**: list, upload dialog with `FormData` file posting, status polling
- **Validation Jobs module**: trigger run dialog, job list with status chips, progress indicator
- `proxy.conf.json` — `/api/*` forwarded to `http://localhost:8000`

---

## [0.3.0] — 2026-02-24

**Phase 1 (continued): Studies, Datasets, Validation, Findings, Reports, Audit API**

### Added
- **Studies API** — CRUD with sponsor/CRO assignment, status lifecycle (`draft → active → locked → archived`)
- **Datasets API** — file upload to local or GCS storage, metadata extraction, CDISC domain detection
- **Validation Engine**:
  - Celery task: load dataset → apply rule suite → write findings to DB → index to Elasticsearch
  - Built-in rules: required fields, date consistency, value range checks, controlled terminology
  - ML anomaly detection via Isolation Forest (`scikit-learn`)
- **Findings API** — paginated list with filters, resolve/waive endpoint, bulk operations
- **Reports API** — async report generation, PDF/JSON output, HMAC e-signature (21 CFR Part 11)
- **Audit Trail API** — append-only log, paginated query with action/user/date filters
- 45 integration tests covering all endpoints (auth, RBAC, data isolation between orgs)

---

## [0.2.0] — 2026-02-10

**Phase 1: Backend Foundation**

### Added
- FastAPI application scaffold (`backend/app/`) with SQLAlchemy 2.0 + Alembic
- **Authentication API**:
  - Registration, login, logout, refresh token
  - JWT RS256 (auto-generates dev key pair on first startup)
  - bcrypt password hashing (`passlib[bcrypt]`, cost factor 12)
  - TOTP MFA enrollment and verification (`pyotp`, RFC 6238)
- **RBAC** — four roles: `sponsor`, `cro_validator`, `cro_admin`, `system_admin`
- `AuditLog` model with SQLAlchemy event listener — every session `flush()` emits an audit record for modified objects
- `docker-compose.yml` — PostgreSQL 16, Redis 7, Elasticsearch 8, FastAPI API, Celery worker
- Alembic initial migration — all tables, indexes, and foreign key constraints
- 62 integration tests covering auth flows, MFA, token refresh, and RBAC enforcement

---

## [0.1.0] — 2026-01-15

**Phase 0: Proof of Concept**

### Added
- Python CLI prototype for rule-based clinical dataset validation
- Isolation Forest anomaly detection for numeric variables (scikit-learn)
- CSV ingestion with Polars for SDTM-like datasets
- Text-based compliance report output
- Modular rule engine: age range, required fields, date consistency, value bounds
- Initial project structure and README

---

[0.8.0]: https://github.com/YOUR_ORG/integris/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/YOUR_ORG/integris/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/YOUR_ORG/integris/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/YOUR_ORG/integris/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/YOUR_ORG/integris/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/YOUR_ORG/integris/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/YOUR_ORG/integris/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/YOUR_ORG/integris/releases/tag/v0.1.0
