# Integris Clinical Platform — Installation Guide

Step-by-step instructions for getting the full stack running on a **fresh Linux machine** (Ubuntu 22.04 / 24.04 or Debian 12). Commands marked with `[Windows]` have PowerShell equivalents.

---

## Prerequisites

### 1. Install Docker Engine (not Docker Desktop)

```bash
# Remove old versions
sudo apt-get remove docker docker-engine docker.io containerd runc

# Install via the official script
curl -fsSL https://get.docker.com | sudo sh

# Add your user to the docker group (log out and back in after this)
sudo usermod -aG docker $USER

# Verify
docker --version          # Docker version 25+
docker compose version    # Docker Compose version v2.24+
```

### 2. Install Python 3.12+

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip
python3 --version   # Python 3.12.x
```

> **Windows:** Download from https://python.org — ensure "Add to PATH" is checked.

### 3. Install Node.js 20+ and npm 10+

```bash
# Via NodeSource (recommended)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node --version   # v20.x or v22.x
npm --version    # 10+
```

> **Windows:** Download from https://nodejs.org (LTS).

### 4. Install git

```bash
sudo apt-get install -y git
git --version
```

---

## Clone the Repository

```bash
git clone https://github.com/YOUR_ORG/integris.git
cd integris
```

> Replace `YOUR_ORG/integris` with the actual repository URL.

---

## Step 1 — Create Your `.env` File

```bash
cp .env.example .env
```

Then open `.env` in your editor and follow the steps below to fill in each placeholder.

### 1a. Generate RSA-2048 JWT keys

```bash
python backend/scripts/generate_keys.py
```

This writes `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` directly into `.env`.

> **Or** use the Makefile shortcut: `make keys`

### 1b. Set a strong database password

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output into `.env`:
```
POSTGRES_PASSWORD=<output>
DATABASE_URL=postgresql://cdtool:<output>@localhost:5432/cdtool
TEST_DATABASE_URL=postgresql://cdtool:<output>@localhost:5432/cdtool_test
```

### 1c. Set the application secret key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output into `.env`:
```
SECRET_KEY=<output>
```

### Final `.env` checklist

| Variable | Status |
|---|---|
| `POSTGRES_PASSWORD` | ✅ set to strong random value |
| `DATABASE_URL` | ✅ password matches above |
| `TEST_DATABASE_URL` | ✅ password matches above |
| `JWT_PRIVATE_KEY` | ✅ populated by `generate_keys.py` |
| `JWT_PUBLIC_KEY` | ✅ populated by `generate_keys.py` |
| `SECRET_KEY` | ✅ set to 64-char hex value |
| `STORAGE_BACKEND` | leave as `local` for development |

---

## Step 2 — Install Python Dependencies (Local Dev)

Create a virtual environment for running tests and scripts locally (outside Docker):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

---

## Step 3 — Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

This installs all Angular 21 + Material packages listed in `frontend/package.json`.

---

## Step 4 — Start All Services with Docker Compose

```bash
make up
```

This builds and starts six containers:

| Container | Port | Purpose |
|---|---|---|
| `db` | 5432 | PostgreSQL 16 |
| `db-init` | — | Creates `cdtool_test` database |
| `redis` | 6379 | Celery broker |
| `elasticsearch` | 9200 | Findings search index |
| `api` | 8000 | FastAPI (hot-reload) |
| `worker` | — | Celery validation worker |

> **First run only:** Elasticsearch takes 30–60 seconds to become healthy. Watch with:
> ```bash
> docker compose logs -f elasticsearch
> ```
> Wait until you see `"message": "started"`.

> **Windows (PowerShell):**
> ```powershell
> .\scripts\run.ps1 up
> ```

---

## Step 5 — Run Database Migrations

Once `db` and `api` containers are healthy:

```bash
make migrate
```

This runs `alembic upgrade head` inside the API container, creating all tables.

Verify migrations applied:
```bash
docker compose exec db psql -U cdtool -d cdtool -c "\dt"
```

You should see tables: `users`, `studies`, `datasets`, `validation_jobs`, `findings`, `reports`, `audit_logs`, etc.

---

## Step 6 — Verify the API is Running

```bash
make health
```

Expected response:
```json
{
    "status": "ok",
    "version": "0.8.0"
}
```

Also check the interactive API docs at: **http://localhost:8000/docs**

---

## Step 7 — Start the Angular Frontend Dev Server

In a second terminal:

```bash
make frontend
```

This runs `ng serve --open` from the `frontend/` directory and opens your browser to **http://localhost:4200**.

The Angular proxy forwards `/api/*` requests to `http://localhost:8000`.

> **Windows (PowerShell):**
> ```powershell
> .\scripts\run.ps1 frontend
> ```

---

## Step 8 — Run the Test Suite

With `db`, `db-init`, and `redis` containers running:

```bash
# Activate the venv if not already active
source .venv/bin/activate

# Run all tests
make test
```

Expected output: **107 tests passing** across auth, studies, datasets, validation, findings, reports, and audit modules.

### Run a specific test module

```bash
make test-auth        # auth tests only
make test-validation  # validation pipeline tests
make test-fast        # stop on first failure (-x)
```

---

## Day-to-Day Workflow

```bash
# Start everything (if not already running)
make up
make migrate          # only needed after pulling new migrations

# In a separate terminal — Angular dev server
make frontend

# Tail API logs
make logs

# Stop everything
make down

# Stop and delete all data (clean slate)
make clean
```

---

## Creating a New Database Migration

After changing a SQLAlchemy model:

```bash
make makemigration msg="add mfa_secret to users"
```

This autogenerates a migration file in `backend/alembic/versions/`. Review it, then:

```bash
make migrate
```

---

## Production Build (Frontend)

To build the Angular app for production deployment:

```bash
make frontend-build
```

Output is written to `frontend/dist/frontend/browser/`. The production Docker image (`infra/docker/frontend/Dockerfile.prod`) picks this up automatically via the `nginx` static server.

---

## Troubleshooting

### Port already in use

```bash
# Find what's using port 5432
sudo ss -tulnp | grep 5432
# If a local Postgres is running, stop it:
sudo systemctl stop postgresql
```

### Elasticsearch won't start (not enough virtual memory)

```bash
# Required by Elasticsearch on Linux
sudo sysctl -w vm.max_map_count=262144

# Make it permanent
echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf
```

### API container exits immediately

```bash
docker compose logs api
```

Common causes:
- `.env` is missing or has blank `JWT_PRIVATE_KEY` → run `make keys`
- Database not yet healthy → wait and re-run `make up`

### `make migrate` fails with "relation already exists"

The database already has the table. Either the migration was applied previously, or you started from a non-empty volume. Check current state:

```bash
docker compose exec db psql -U cdtool -d cdtool -c "SELECT version_num FROM alembic_version;"
```

### Tests fail with `connection refused`

The test database container `db-init` must have run successfully. Check:

```bash
docker compose logs db-init
docker compose exec db psql -U cdtool -d cdtool -c "SELECT datname FROM pg_database;"
```

If `cdtool_test` is missing:
```bash
docker compose up -d db-init
```

### `npm install` fails with peer dependency errors

Node.js version too old. Verify:
```bash
node --version   # must be 20.x or 22.x
npm --version    # must be 10+
```

### Permission denied on `docker` commands

You haven't logged out after adding yourself to the `docker` group. Either log out and back in, or run:
```bash
newgrp docker
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_USER` | Yes | PostgreSQL username (default: `cdtool`) |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `POSTGRES_DB` | Yes | Main database name (default: `cdtool`) |
| `DATABASE_URL` | Yes | Full SQLAlchemy connection string |
| `TEST_DATABASE_URL` | Yes | Test database connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `ELASTICSEARCH_URL` | Yes | Elasticsearch base URL |
| `JWT_PRIVATE_KEY` | Yes | RSA-2048 private key (PEM, `\n`-escaped) |
| `JWT_PUBLIC_KEY` | Yes | RSA-2048 public key (PEM, `\n`-escaped) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | Default: 30 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | Default: 7 |
| `SECRET_KEY` | Yes | HMAC secret for e-signatures (64-char hex) |
| `STORAGE_BACKEND` | Yes | `local` or `gcs` |
| `STORAGE_LOCAL_PATH` | If local | Path for uploaded files (default: `./storage`) |
| `GCS_BUCKET_NAME` | If GCS | Google Cloud Storage bucket name |
| `GCS_PROJECT_ID` | If GCS | Google Cloud project ID |
| `DEBUG` | No | `true` enables FastAPI debug mode |
| `ENVIRONMENT` | No | `development` / `staging` / `production` |
