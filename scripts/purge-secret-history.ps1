<#
.SYNOPSIS
    Emergency script: removes .env (and any secret files) from ALL git history,
    then force-pushes to overwrite the public GitHub repo.

.DESCRIPTION
    Run this ONCE from the project root on a FRESH CLONE of the repo.
    Do NOT run on a working copy you care about — it rewrites history.

    Prerequisites:
        pip install git-filter-repo          (once, globally)
        gh auth login                        (GitHub CLI, for the API call)

.PARAMETER RepoUrl
    HTTPS URL of the GitHub repo, e.g. https://github.com/yourorg/CDTool.git

.PARAMETER Branch
    Branch to rewrite (default: main)

.EXAMPLE
    .\scripts\purge-secret-history.ps1 -RepoUrl https://github.com/yourorg/CDTool.git
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$RepoUrl,

    [Parameter(Mandatory = $false)]
    [string]$Branch = "main"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "`n========================================================" -ForegroundColor Red
Write-Host " SECURITY INCIDENT RESPONSE — History Purge" -ForegroundColor Red
Write-Host "========================================================`n" -ForegroundColor Red

# ── Step 1: Verify git-filter-repo is installed ───────────────────────────────
Write-Host "[1/7] Checking git-filter-repo..." -ForegroundColor Cyan
$filterRepo = git filter-repo --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "      Not found. Installing via pip..." -ForegroundColor Yellow
    pip install git-filter-repo
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Could not install git-filter-repo. Run: pip install git-filter-repo" -ForegroundColor Red
        exit 1
    }
}
Write-Host "      OK" -ForegroundColor Green

# ── Step 2: Create a FRESH bare clone in a temp directory ─────────────────────
Write-Host "[2/7] Creating fresh clone of $RepoUrl ..." -ForegroundColor Cyan
$tmpDir = Join-Path $env:TEMP ("cdtool-purge-" + (Get-Date -Format "yyyyMMddHHmmss"))
New-Item -ItemType Directory -Path $tmpDir | Out-Null
Set-Location $tmpDir

git clone --mirror $RepoUrl repo.git
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: git clone failed" -ForegroundColor Red; exit 1 }
Set-Location (Join-Path $tmpDir "repo.git")
Write-Host "      Cloned to $tmpDir\repo.git" -ForegroundColor Green

# ── Step 3: Identify which paths to purge ─────────────────────────────────────
Write-Host "[3/7] Scanning history for secret files..." -ForegroundColor Cyan
$secretPaths = @(
    ".env",
    "backend/.env",
    "backend/backend/.env",
    ".env.local",
    "*.pem",
    "*.key"
)

$found = @()
foreach ($p in $secretPaths) {
    $hits = git log --all --full-history -- $p 2>&1
    if ($hits) { $found += $p; Write-Host "      FOUND in history: $p" -ForegroundColor Yellow }
}

if ($found.Count -eq 0) {
    Write-Host "      No secret files found in history. Nothing to purge." -ForegroundColor Green
    Write-Host "      (The files may already have been removed, or were never committed.)" -ForegroundColor Gray
    Set-Location $env:TEMP
    Remove-Item $tmpDir -Recurse -Force
    exit 0
}

# ── Step 4: Rewrite history with git-filter-repo ──────────────────────────────
Write-Host "[4/7] Rewriting history (removing secret files)..." -ForegroundColor Cyan
$pathArgs = ($found | ForEach-Object { "--path `"$_`"" }) -join " "
$cmd = "git filter-repo --invert-paths $pathArgs --force"
Write-Host "      Running: $cmd" -ForegroundColor Gray
Invoke-Expression $cmd
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: git-filter-repo failed" -ForegroundColor Red
    exit 1
}
Write-Host "      History rewritten successfully." -ForegroundColor Green

# ── Step 5: Verify the files are gone ─────────────────────────────────────────
Write-Host "[5/7] Verifying removal..." -ForegroundColor Cyan
$stillFound = @()
foreach ($p in $found) {
    $hits = git log --all --full-history -- $p 2>&1
    if ($hits) { $stillFound += $p }
}
if ($stillFound.Count -gt 0) {
    Write-Host "ERROR: These paths still appear in history: $($stillFound -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "      Verified — secret files no longer exist in ANY commit." -ForegroundColor Green

# ── Step 6: Force-push to GitHub ──────────────────────────────────────────────
Write-Host "[6/7] Force-pushing rewritten history to GitHub..." -ForegroundColor Cyan
Write-Host "      This is IRREVERSIBLE. Collaborators will need to re-clone." -ForegroundColor Yellow
$confirm = Read-Host "      Type YES to force-push"
if ($confirm -ne "YES") { Write-Host "Aborted. No changes pushed."; exit 0 }

git push --force --all
git push --force --tags
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Force push failed. You may need to disable branch protection temporarily." -ForegroundColor Red
    Write-Host "       GitHub → Settings → Branches → Uncheck 'Require pull request reviews'" -ForegroundColor Yellow
    exit 1
}
Write-Host "      Force-pushed successfully." -ForegroundColor Green

# ── Step 7: Invalidate GitHub's cache ─────────────────────────────────────────
Write-Host "[7/7] Requesting GitHub cache invalidation..." -ForegroundColor Cyan
Write-Host "      GitHub caches objects for up to 90 days." -ForegroundColor Gray
Write-Host "      You MUST contact GitHub Support to clear their caches:" -ForegroundColor Yellow
Write-Host "      https://support.github.com/contact" -ForegroundColor Yellow
Write-Host "      Tell them: 'RSA private key and database password accidentally" -ForegroundColor Yellow
Write-Host "      committed. History rewritten. Please invalidate all caches for" -ForegroundColor Yellow
Write-Host "      repo $RepoUrl'" -ForegroundColor Yellow

Write-Host @"

========================================================
 PURGE COMPLETE — Action items remaining:
========================================================

  1. DONE   New RSA keys are in your .env (already rotated locally).
  2. DONE   POSTGRES_PASSWORD rotated in .env.
  3. TODO   Rotate the DB password in your RUNNING Docker environment:
               docker compose exec db psql -U postgres -c \
               "ALTER USER cdtool PASSWORD '<new-password-from-.env>';"
  4. TODO   Notify all collaborators to DELETE their local clone and re-clone.
  5. TODO   Contact GitHub Support (link above) to purge server-side caches.
  6. TODO   Check GitHub → Insights → Traffic → Clones to see if anyone cloned
            the repo while the .env was exposed. If yes, treat all exposed
            credentials as compromised and notify your security team.
  7. TODO   Scan your git log for any other secrets (API keys, tokens, etc.):
               git log --all --full-history --diff-filter=A -- '*.json' | head -50

"@ -ForegroundColor Green

# Cleanup
Set-Location $env:USERPROFILE
Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
