# Integris Clinical Platform — GCP Infrastructure

## Architecture

```
Internet
   │
   ▼
Cloud Armor WAF  ──────────────────────────────── rate-limit / OWASP CRS
   │
Global HTTPS Load Balancer  (TLS 1.3, Google-managed SSL cert)
   │
Cloud Run (API)     Cloud Run (Worker)
   │                      │
   └──── VPC Connector ───┘
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
Cloud SQL   Memorystore  Cloud Storage
(Postgres)   (Redis)    (Datasets/Reports)
     │
Secret Manager  ──  KMS (CMEK)
```

## Prerequisites

```bash
# Install tools
brew install terraform google-cloud-sdk

# Authenticate
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_GCP_PROJECT_ID
```

## First-time Bootstrap

### 1. Create the Terraform state bucket (one-time, manual)

```bash
gsutil mb -p YOUR_GCP_PROJECT_ID -l us-central1 gs://YOUR_GCP_PROJECT_ID-tfstate
gsutil versioning set on gs://YOUR_GCP_PROJECT_ID-tfstate
```

### 2. Apply the dev environment

```bash
cd infra/terraform/environments/dev

terraform init
terraform plan -var="db_password=$DB_PASSWORD" -out=tfplan
terraform apply tfplan
```

Pass the DB password via environment variable — **never** put it in `terraform.tfvars`:

```bash
export TF_VAR_db_password="$(openssl rand -base64 32)"
```

### 3. Seed secrets that Terraform cannot auto-generate

After `terraform apply`, three secrets need manual values in Secret Manager:

```bash
ENV=dev
PROJECT=YOUR_GCP_PROJECT_ID

# JWT keys — generate fresh pair
python backend/scripts/generate_keys.py > /tmp/keys.txt

gcloud secrets versions add integris-${ENV}-JWT_PRIVATE_KEY \
  --data-file=<(grep PRIVATE /tmp/keys.txt | cut -d= -f2-)

gcloud secrets versions add integris-${ENV}-JWT_PUBLIC_KEY \
  --data-file=<(grep PUBLIC /tmp/keys.txt | cut -d= -f2-)

gcloud secrets versions add integris-${ENV}-SECRET_KEY \
  --data-file=<(python -c "import secrets; print(secrets.token_hex(32))")

gcloud secrets versions add integris-${ENV}-ELASTICSEARCH_URL \
  --data-file=<(echo "https://YOUR_ELASTIC_CLOUD_URL:443")

rm /tmp/keys.txt
```

### 4. Create the migration Cloud Run Job

```bash
REGISTRY=us-central1-docker.pkg.dev/YOUR_GCP_PROJECT_ID/integris-images
ENV=dev

gcloud run jobs create ${ENV}-migrate \
  --image=${REGISTRY}/backend:latest \
  --region=us-central1 \
  --command=sh \
  --args="-c,cd /app/backend && alembic upgrade head" \
  --set-secrets=DATABASE_URL=integris-${ENV}-DATABASE_URL:latest \
  --vpc-connector=integris-${ENV}-connector \
  --service-account=integris-${ENV}-run-sa@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com \
  --max-retries=1 \
  --task-timeout=300
```

### 5. Point your DNS

After `terraform output lb_ip`, add a DNS A record:

```
dev.integris.YOUR_DOMAIN.com  →  <lb_ip>
```

SSL certificate provisioning takes ~15 minutes after DNS propagates.

---

## CI/CD Triggers

Create these triggers in Cloud Build (GCP Console → Cloud Build → Triggers):

| Trigger | Event | Config file | Env |
|---|---|---|---|
| PR check | PR to `main` | `infra/cloudbuild/cloudbuild-pr.yaml` | — |
| Dev deploy | Push to `main` | `infra/cloudbuild/cloudbuild.yaml` | `_ENV=dev` |
| Staging deploy | Push to `staging` | `infra/cloudbuild/cloudbuild.yaml` | `_ENV=staging`, services=staging |
| Prod deploy | Tag `v*.*.*` | `infra/cloudbuild/cloudbuild-prod.yaml` | — |

---

## Environment Differences

| Setting | Dev | Staging | Prod |
|---|---|---|---|
| SQL tier | db-g1-small | db-g1-small | db-custom-2-7680 |
| SQL HA | ZONAL | ZONAL | REGIONAL |
| SQL backups | 3 days | 7 days | 30 days |
| Redis tier | BASIC | STANDARD_HA | STANDARD_HA |
| Redis memory | 1 GB | 2 GB | 5 GB |
| API min instances | 0 (scale-to-zero) | 1 | 2 |
| API max instances | 3 | 5 | 20 |
| CMEK | ✗ | ✓ | ✓ |
| Cloud Armor | ✗ | ✓ | ✓ |
| Deletion protection | ✗ | ✗ | ✓ |

---

## HIPAA Controls Implemented

| Control | Implementation |
|---|---|
| Encryption at rest | CMEK via Cloud KMS (staging/prod) |
| Encryption in transit | TLS 1.3 enforced at LB; Cloud SQL SSL_ONLY; Redis TLS |
| Private networking | Cloud SQL: private IP only; Redis: VPC-internal only |
| Audit logging | pgAudit on Cloud SQL; Cloud Logging on all services; app-level audit trail in DB |
| Access control | Service accounts with least-privilege; RBAC in app |
| WAF | Cloud Armor OWASP CRS, rate limiting, brute-force protection on auth |
| Backup | Automated SQL backups; GCS versioning on all buckets |
| Data retention | Reports: 7-year retention; Nearline → Coldline lifecycle |
| Secrets management | Secret Manager with CMEK; no secrets in environment config |

---

## Day-2 Operations

### Manual migration run

```bash
gcloud run jobs execute prod-migrate --region=us-central1 --wait
```

### Roll back a bad deployment

```bash
# List recent revisions
gcloud run revisions list --service=integris-prod-api --region=us-central1

# Route 100% traffic back to previous revision
gcloud run services update-traffic integris-prod-api \
  --region=us-central1 \
  --to-revisions=integris-prod-api-PREVIOUS_HASH=100
```

### Force a secret rotation

```bash
# Generate new JWT keys
python backend/scripts/generate_keys.py > /tmp/new-keys.txt

gcloud secrets versions add integris-prod-JWT_PRIVATE_KEY \
  --data-file=<(grep PRIVATE /tmp/new-keys.txt | cut -d= -f2-)

# Cloud Run picks up the new version on next request (version=latest)
rm /tmp/new-keys.txt
```

### Check service health

```bash
curl https://app.integris.YOUR_DOMAIN.com/health
```

### Destroy dev environment

```bash
cd infra/terraform/environments/dev
terraform destroy -var="db_password=$TF_VAR_db_password"
```
