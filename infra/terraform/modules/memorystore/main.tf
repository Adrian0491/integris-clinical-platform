# =============================================================================
# Memorystore Redis — Celery broker + result backend
# HIPAA: in-transit encryption (TLS), AUTH token, private VPC only
# =============================================================================

locals {
  prefix = "${var.app_name}-${var.environment}"
}

resource "google_redis_instance" "main" {
  project            = var.project_id
  name               = "${local.prefix}-redis"
  region             = var.region
  tier               = var.tier
  memory_size_gb     = var.memory_size_gb
  redis_version      = var.redis_version
  authorized_network = var.vpc_network_id

  # ── Security ──────────────────────────────────────────────────────────────
  auth_enabled            = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"  # TLS

  # ── Maintenance ───────────────────────────────────────────────────────────
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }

  labels = var.labels
}
