# =============================================================================
# Dev environment — scales to zero, no HA, no CMEK, no Cloud Armor
# Mirrors production topology without the cost
# =============================================================================

project_id  = "YOUR_GCP_PROJECT_ID"
region      = "us-central1"
environment = "dev"
app_name    = "integris"
domain_name = "dev.integris.YOUR_DOMAIN.com"
alert_email = "eng@YOUR_DOMAIN.com"

# ── Cloud SQL ─────────────────────────────────────────────────────────────────
sql_tier               = "db-g1-small"
sql_availability_type  = "ZONAL"
sql_disk_size_gb       = 10
sql_backup_days        = 3
point_in_time_recovery = false
sql_deletion_protection = false

# ── Memorystore ───────────────────────────────────────────────────────────────
redis_tier         = "BASIC"
redis_memory_gb    = 1

# ── Cloud Run ─────────────────────────────────────────────────────────────────
api_min_instances    = 0    # scale to zero
api_max_instances    = 3
api_cpu              = "1"
api_memory           = "512Mi"
worker_min_instances = 0
worker_max_instances = 2
worker_cpu           = "1"
worker_memory        = "512Mi"

# ── Features ──────────────────────────────────────────────────────────────────
enable_cmek         = false
enable_cloud_armor  = false
