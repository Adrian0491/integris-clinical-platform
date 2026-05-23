# Security Policy — Integris Clinical Platform

**Integris Clinical Services LLC** takes the security of its platform seriously. The Integris Clinical Platform processes Protected Health Information (PHI) and is designed to meet HIPAA Security Rule requirements. We appreciate responsible disclosure from security researchers.

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately to:

**Email**: security@integris-clinical.com  
**Subject line**: `[SECURITY] <brief description>`  
**PGP key**: Available on request

### What to include

- Description of the vulnerability and its potential impact
- Steps to reproduce (including any proof-of-concept code or payloads)
- Affected version(s) or component(s)
- Any suggested mitigations, if known

### Our commitment

| Milestone | Target |
|---|---|
| Initial acknowledgement | Within 2 business days |
| Triage and severity assessment | Within 5 business days |
| Remediation plan communicated | Within 10 business days |
| Fix deployed (Critical/High) | Within 30 days |
| Fix deployed (Medium/Low) | Within 90 days |
| Credit in CHANGELOG | Upon fix release, with researcher's consent |

We follow the **coordinated disclosure** model: we ask that reporters allow us reasonable time to remediate before public disclosure.

---

## Supported Versions

| Version | Supported |
|---|---|
| 0.8.x (current) | ✅ Full support |
| 0.7.x | ⚠️ Security fixes only |
| < 0.7 | ❌ End of life — please upgrade |

---

## Scope

### In scope

- The Integris Clinical Platform API (`/api/v1/*`)
- The Angular frontend application
- Authentication and session management (JWT, MFA, refresh tokens)
- Role-based access control enforcement
- Audit trail integrity
- Electronic signature mechanism (21 CFR Part 11)
- File upload handling and storage
- GCP infrastructure configuration (Terraform)

### Out of scope

- Denial-of-service attacks that require significant resources to execute
- Social engineering of Integris staff or customers
- Physical security of our facilities
- Third-party services we do not control (GCP, Elasticsearch Cloud)
- Vulnerabilities in dependencies that are already publicly known and tracked upstream
- Issues in development or staging environments accessed with your own credentials

---

## Security Architecture

### Authentication

- **JWT RS256** — asymmetric key signing; private key stored in GCP Secret Manager, never in application config
- **Access tokens**: 30-minute TTL, rotated on every refresh
- **Refresh tokens**: 7-day TTL, single-use (reuse detection triggers forced logout)
- **TOTP MFA** (RFC 6238) — required for Validator and Admin roles
- **bcrypt** password hashing (cost factor ≥ 12)

### Encryption

| Layer | Method |
|---|---|
| Data at rest (Cloud SQL) | Cloud KMS CMEK (staging/prod) |
| Data at rest (Cloud Storage) | Cloud KMS CMEK (staging/prod) |
| Data at rest (Secret Manager) | Cloud KMS CMEK |
| Data in transit (HTTPS) | TLS 1.3, `RESTRICTED` cipher policy |
| Data in transit (Cloud SQL) | `ssl_mode = ENCRYPTED_ONLY` |
| Data in transit (Redis) | TLS + AUTH token |

### Network security

- Cloud SQL: private IP only — no public interface
- Redis: VPC-internal only — no public interface
- Cloud Run: egress restricted to private ranges via VPC connector
- Cloud Armor WAF: OWASP CRS (SQLi, XSS, LFI, RFI rules), rate limiting, adaptive L7 DDoS protection
- Auth endpoint: 20 requests/minute per IP (brute-force protection)

### Audit trail

- Every write to clinical data, user accounts, studies, findings, and reports emits an immutable `audit_log` record
- Audit records include: timestamp, user ID, action, resource type, resource ID, source IP, request metadata
- pgAudit enabled on Cloud SQL for database-level query logging
- All audit logs shipped to Cloud Logging with 7-year retention

### Access control

- **RBAC** with four roles: `sponsor`, `cro_validator`, `cro_admin`, `system_admin`
- Every API endpoint is decorated with a role guard — unauthenticated and unauthorized requests return 401/403 (never 200 with empty data)
- Service accounts on GCP use least-privilege IAM bindings

### Secret management

- No secrets in Docker images, environment config files, or application code
- All production secrets stored in GCP Secret Manager
- Secrets accessed via Cloud Run's native secret injection (`secretAccessor` IAM role)
- Secret rotation: JWT keys rotated quarterly; Cloud Run picks up `latest` version without redeployment

---

## HIPAA Security Rule Alignment

| Safeguard | § | Implementation |
|---|---|---|
| Access control | 164.312(a)(1) | RBAC, JWT, MFA |
| Audit controls | 164.312(b) | Immutable audit log, pgAudit, Cloud Logging |
| Integrity | 164.312(c)(1) | HMAC e-signatures, DB constraints, FK integrity |
| Transmission security | 164.312(e)(1) | TLS 1.3 end-to-end |
| Encryption at rest | 164.312(a)(2)(iv) | CMEK via Cloud KMS |
| Automatic logoff | 164.312(a)(2)(iii) | 30-minute access token TTL |
| Backup and recovery | 164.308(a)(7) | Automated PITR on Cloud SQL; GCS versioning |

---

## Dependency Vulnerability Management

We monitor production dependencies for known CVEs using:

- GitHub Dependabot alerts (Python + npm)
- `pip-audit` run in CI on every pull request to `main`
- `npm audit` run in CI on every pull request to `main`

Critical and High CVEs in production dependencies are treated as security incidents and patched within 30 days.

---

## Bug Bounty

We do not currently operate a formal paid bug bounty program. We do publicly credit researchers in our CHANGELOG when they responsibly disclose vulnerabilities, with their consent.

---

© 2026 Integris Clinical Services LLC
