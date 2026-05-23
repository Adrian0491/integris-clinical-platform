# =============================================================================
# Production environment — HA, CMEK, Cloud Armor, deletion protection on
# Treat changes here as high-risk: plan + peer-review before apply
# =============================================================================

project_id  = "YOUR_GCP_PROJECT_ID"
region      = "us-central1"
environment = "prod"
app_name    = "integris"
domain_name = "app.integris.YOUR_DOMAIN.com"
alert_email = "oncall@YOUR_DOMAIN.com"

# ── Cloud SQL — db-custom-2-7680 = 2 vCPU / 7.5 GB RAM ──────────────────────
sql_tier               = "db-custom-2-7680"
sql_availability_type  = "REGIONAL"   # synchronous HA replica
sql_disk_size_gb       = 100
sql_backup_days        = 30
point_in_time_recovery = true
sql_deletion_protection = true

# ── Memorystore ───────────────────────────────────────────────────────────────
redis_tier         = "STANDARD_HA"
redis_memory_gb    = 5

# ── Cloud Run ─────────────────────────────────────────────────────────────────
api_min_instances    = 2    # always-warm — no cold starts for CRO users
api_max_instances    = 20
api_cpu              = "2"
api_memory           = "1Gi"
worker_min_instances = 1
worker_max_instances = 10
worker_cpu           = "2"
worker_memory        = "2Gi"

# ── Features ──────────────────────────────────────────────────────────────────
enable_cmek        = true
enable_cloud_armor = true
