# =============================================================================
# Secret Manager — application secrets with CMEK and IAM access control
# Secrets created here are shells; values are populated out-of-band or via
# the secrets variable (sensitive). Cloud Run SA gets secretAccessor role.
# =============================================================================

locals {
  prefix   = "${var.app_name}-${var.environment}"
  use_cmek = var.kms_key_id != ""

  # Canonical list of all application secrets
  secret_names = [
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_PRIVATE_KEY",
    "JWT_PUBLIC_KEY",
    "SECRET_KEY",
    "ELASTICSEARCH_URL",
    "GCS_BUCKET_DATASETS",
    "GCS_BUCKET_REPORTS",
  ]
}

# ── Create secret shells ───────────────────────────────────────────────────────
resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(local.secret_names)
  project   = var.project_id
  secret_id = "${local.prefix}-${each.key}"

  labels = var.labels

  replication {
    user_managed {
      replicas {
        location = var.region
        dynamic "customer_managed_encryption" {
          for_each = local.use_cmek ? [var.kms_key_id] : []
          content { kms_key_name = customer_managed_encryption.value }
        }
      }
    }
  }
}

# ── Optionally write initial secret values (from var.secrets map) ─────────────
resource "google_secret_manager_secret_version" "initial" {
  for_each = {
    for k, v in var.secrets : k => v
    if contains(local.secret_names, k)
  }

  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value

  lifecycle {
    ignore_changes = [secret_data]   # never overwrite after first apply
  }
}

# ── Grant Cloud Run service account access to all secrets ─────────────────────
resource "google_secret_manager_secret_iam_member" "cloud_run_accessor" {
  for_each  = toset(local.secret_names)
  project   = var.project_id
  secret_id = google_secret_manager_secret.secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.cloud_run_sa_email}"
}
