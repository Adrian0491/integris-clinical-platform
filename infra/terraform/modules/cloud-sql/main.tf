# =============================================================================
# Cloud SQL — PostgreSQL 16 with private IP, CMEK, automated backups
# HIPAA: no public IP, SSL enforced, audit logs via Cloud Logging
# =============================================================================

locals {
  prefix        = "${var.app_name}-${var.environment}"
  use_cmek      = var.kms_key_id != ""
}

resource "google_sql_database_instance" "main" {
  project             = var.project_id
  name                = "${local.prefix}-pg"
  database_version    = var.database_version
  region              = var.region
  deletion_protection = var.deletion_protection

  # CMEK encryption
  dynamic "encryption_key_name" {
    for_each = local.use_cmek ? [var.kms_key_id] : []
    content  { value = encryption_key_name.value }
  }

  settings {
    tier              = var.tier
    availability_type = var.availability_type
    disk_autoresize   = true
    disk_size         = var.disk_size_gb
    disk_type         = "PD_SSD"

    user_labels = var.labels

    # ── Private IP only — no public IP ──────────────────────────────────────
    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = var.vpc_network_id
      enable_private_path_for_google_cloud_services = true
      ssl_mode                                      = "ENCRYPTED_ONLY"   # TLS enforced
    }

    # ── Automated backups ────────────────────────────────────────────────────
    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      location                       = var.region
      point_in_time_recovery_enabled = var.point_in_time_recovery
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = var.backup_retention_days
        retention_unit   = "COUNT"
      }
    }

    # ── Maintenance window ───────────────────────────────────────────────────
    maintenance_window {
      day          = 7    # Sunday
      hour         = 3    # 03:00 UTC
      update_track = "stable"
    }

    # ── Performance insights ─────────────────────────────────────────────────
    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }

    # ── Database flags ───────────────────────────────────────────────────────
    database_flags {
      name  = "log_checkpoints"
      value = "on"
    }
    database_flags {
      name  = "log_connections"
      value = "on"
    }
    database_flags {
      name  = "log_disconnections"
      value = "on"
    }
    database_flags {
      name  = "log_lock_waits"
      value = "on"
    }
    database_flags {
      name  = "log_min_duration_statement"
      value = "1000"   # log queries taking > 1 s
    }
    database_flags {
      name  = "cloudsql.enable_pg_audit"
      value = "on"     # pgAudit extension for 21 CFR Part 11
    }
  }

  depends_on = [var.private_vpc_connection_id]
}

# ── Database ──────────────────────────────────────────────────────────────────
resource "google_sql_database" "main" {
  project  = var.project_id
  instance = google_sql_database_instance.main.name
  name     = var.db_name
}

# ── Database user ─────────────────────────────────────────────────────────────
resource "google_sql_user" "app" {
  project  = var.project_id
  instance = google_sql_database_instance.main.name
  name     = var.db_user
  password = var.db_password
}
