<#
.SYNOPSIS
    CDTool developer workflow — Windows PowerShell version of the Makefile.

.DESCRIPTION
    Run from the project root (CDTool\):
        .\scripts\run.ps1 up
        .\scripts\run.ps1 migrate
        .\scripts\run.ps1 test

.PARAMETER Command
    The workflow command to execute. See the list below.
#>

param(
    [Parameter(Position = 0, Mandatory = $false)]
    [string]$Command = "help"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Resolve project root (the directory this script is called from)
$ProjectRoot = (Get-Location).Path
$Backend     = Join-Path $ProjectRoot "backend"

# ── Helpers ───────────────────────────────────────────────────────────────────

function Invoke-Step([string]$Label, [scriptblock]$Block) {
    Write-Host "`n==> $Label" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Label (exit $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Test-DockerRunning {
    $null = docker info 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker Desktop is not running. Start it and try again." -ForegroundColor Red
        exit 1
    }
}

# ── Commands ──────────────────────────────────────────────────────────────────

switch ($Command.ToLower()) {

    "help" {
        Write-Host @"

  CDTool developer commands  (.\scripts\run.ps1 <command>)

  Infrastructure
    up           Start all services (db, redis, elasticsearch, api, worker)
    up-infra     Start only db, redis, elasticsearch  (no app containers)
    down         Stop all services
    clean        Stop services and remove volumes  ** DESTROYS DATA **
    build        Rebuild Docker images without cache
    health       Check the API /health endpoint
    logs         Tail FastAPI container logs
    logs-all     Tail all service logs

  Database
    migrate      Run Alembic migrations  (upgrade head)
    migrate-down Downgrade one migration step
    makemigration  Autogenerate a migration  -msg "describe change"

  Security
    keys         Generate RSA-2048 JWT key pair and write to .env

  Frontend
    frontend       Start Angular dev server with API proxy (opens browser)
    frontend-build Production build to frontend\dist\

  Testing  (requires db + db-init to be running)
    test         Run the full integration test suite
    test-fast    Run tests, stop on first failure  (-x)
    test-auth    Auth tests only
    test-studies Studies tests only
    test-validation Validation tests only
    test-findings   Findings tests only

"@
    }

    # ── Infrastructure ────────────────────────────────────────────────────────

    "up" {
        Test-DockerRunning
        Invoke-Step "Building and starting all services" {
            docker compose up -d --build
        }
        Write-Host @"

  Services are starting up.
  Wait ~30 s for Elasticsearch, then run:  .\scripts\run.ps1 migrate

  API:            http://localhost:8000
  API docs (dev): http://localhost:8000/docs
  PostgreSQL:     localhost:5432
  Elasticsearch:  http://localhost:9200

"@ -ForegroundColor Green
    }

    "up-infra" {
        Test-DockerRunning
        Invoke-Step "Starting infrastructure services only" {
            docker compose up -d db db-init redis elasticsearch
        }
        Write-Host "  Run '.\scripts\run.ps1 migrate' once the db is healthy." -ForegroundColor Green
    }

    "down" {
        Test-DockerRunning
        Invoke-Step "Stopping all services" { docker compose down }
    }

    "clean" {
        Test-DockerRunning
        $confirm = Read-Host "This will destroy all volume data. Type YES to continue"
        if ($confirm -ne "YES") { Write-Host "Aborted."; exit 0 }
        Invoke-Step "Stopping services and removing volumes" { docker compose down -v }
        Write-Host "  All data removed." -ForegroundColor Yellow
    }

    "build" {
        Test-DockerRunning
        Invoke-Step "Rebuilding Docker images (no cache)" {
            docker compose build --no-cache
        }
    }

    "health" {
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
            Write-Host ($resp | ConvertTo-Json) -ForegroundColor Green
        } catch {
            Write-Host "API not reachable — is 'up' running?" -ForegroundColor Red
        }
    }

    "logs" {
        Test-DockerRunning
        docker compose logs -f api
    }

    "logs-all" {
        Test-DockerRunning
        docker compose logs -f
    }

    # ── Database ──────────────────────────────────────────────────────────────

    "migrate" {
        Test-DockerRunning
        Invoke-Step "Running Alembic migrations (upgrade head)" {
            docker compose exec api sh -c "cd /app/backend && alembic upgrade head"
        }
        Write-Host "  Migrations applied." -ForegroundColor Green
    }

    "migrate-down" {
        Test-DockerRunning
        Invoke-Step "Downgrading one migration step" {
            docker compose exec api sh -c "cd /app/backend && alembic downgrade -1"
        }
    }

    "makemigration" {
        Test-DockerRunning
        if (-not $args -or $args.Count -eq 0) {
            $msg = Read-Host "Migration message"
        } else {
            $msg = $args -join " "
        }
        Invoke-Step "Autogenerating migration: '$msg'" {
            docker compose exec api sh -c "cd /app/backend && alembic revision --autogenerate -m '$msg'"
        }
    }

    # ── Frontend ──────────────────────────────────────────────────────────────

    "frontend" {
        $Frontend = Join-Path $ProjectRoot "frontend"
        Push-Location $Frontend
        try {
            Write-Host "  Starting Angular dev server → http://localhost:4200" -ForegroundColor Cyan
            Write-Host "  API requests proxied to     → http://localhost:8000" -ForegroundColor Cyan
            Write-Host ""
            npx ng serve --open
        } finally {
            Pop-Location
        }
    }

    "frontend-build" {
        $Frontend = Join-Path $ProjectRoot "frontend"
        Push-Location $Frontend
        try {
            Invoke-Step "Building Angular app (production)" {
                npx ng build --configuration production
            }
            Write-Host "  Build output: frontend\dist\" -ForegroundColor Green
        } finally {
            Pop-Location
        }
    }

    # ── Security ──────────────────────────────────────────────────────────────

    "keys" {
        Invoke-Step "Generating RSA-2048 JWT key pair" {
            python backend\scripts\generate_keys.py
        }
        Write-Host "  Keys written to .env" -ForegroundColor Green
        Write-Host "  Restart services: .\scripts\run.ps1 down  then  .\scripts\run.ps1 up  then  .\scripts\run.ps1 migrate" -ForegroundColor Yellow
    }

    # ── Testing ───────────────────────────────────────────────────────────────

    "test" {
        Push-Location $Backend
        $env:PYTHONPATH = "$ProjectRoot;$Backend"
        try {
            Invoke-Step "Running full integration test suite" { pytest tests/ -v }
        } finally {
            Pop-Location
            $env:PYTHONPATH = ""
        }
    }

    "test-fast" {
        Push-Location $Backend
        $env:PYTHONPATH = "$ProjectRoot;$Backend"
        try {
            Invoke-Step "Running tests (stop on first failure)" { pytest tests/ -v -x }
        } finally {
            Pop-Location
            $env:PYTHONPATH = ""
        }
    }

    "test-auth" {
        Push-Location $Backend
        $env:PYTHONPATH = "$ProjectRoot;$Backend"
        try {
            Invoke-Step "Running auth tests" { pytest tests/test_auth.py -v }
        } finally {
            Pop-Location
            $env:PYTHONPATH = ""
        }
    }

    "test-studies" {
        Push-Location $Backend
        $env:PYTHONPATH = "$ProjectRoot;$Backend"
        try {
            Invoke-Step "Running studies tests" { pytest tests/test_studies.py -v }
        } finally {
            Pop-Location
            $env:PYTHONPATH = ""
        }
    }

    "test-validation" {
        Push-Location $Backend
        $env:PYTHONPATH = "$ProjectRoot;$Backend"
        try {
            Invoke-Step "Running validation tests" { pytest tests/test_validation.py -v }
        } finally {
            Pop-Location
            $env:PYTHONPATH = ""
        }
    }

    "test-findings" {
        Push-Location $Backend
        $env:PYTHONPATH = "$ProjectRoot;$Backend"
        try {
            Invoke-Step "Running findings tests" { pytest tests/test_findings.py -v }
        } finally {
            Pop-Location
            $env:PYTHONPATH = ""
        }
    }

    default {
        Write-Host "Unknown command: '$Command'.  Run .\scripts\run.ps1 help" -ForegroundColor Red
        exit 1
    }
}
