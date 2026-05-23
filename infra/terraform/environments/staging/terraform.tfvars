# =============================================================================
# Staging environment — production-equivalent topology, smaller instances
# Used for integration testing and UAT before prod deploys
# =============================================================================

project_id  = "YOUR_GCP_PROJECT_ID"
region      = "us-central1"
environment = "staging"
app_name    = "integris"
domain_name = "staging.integris.YOUR_DOMAIN.com"
alert_email = "eng@YOUR_DOMAIN.com"

# ── Cloud SQL ─────────────────────────────────────────────────────────────────
sql_tier               = "db-g1-small"
sql_availability_type  = "ZONAL"
sql_disk_size_gb       = 20
sql_backup_days        = 7
point_in_time_recovery = true
sql_deletion_protection = false

# ── Memorystore ───────────────────────────────────────────────────────────────
redis_tier         = "STANDARD_HA"
redis_memory_gb    = 2

# ── Cloud Run ─────────────────────────────────────────────────────────────────
api_min_instances    = 1
api_max_instances    = 5
api_cpu              = "1"
api_memory           = "512Mi"
worker_min_instances = 1
worker_max_instances = 3
worker_cpu           = "1"
worker_memory        = "1Gi"

# ── Features ──────────────────────────────────────────────────────────────────
enable_cmek        = true
enable_cloud_armor = true
