# =============================================================================
# KMS — Customer-Managed Encryption Keys (CMEK) for HIPAA compliance
# Creates one key ring with separate keys for SQL, Storage, and Secrets.
# =============================================================================

locals {
  prefix = "${var.app_name}-${var.environment}"
}

resource "google_kms_key_ring" "main" {
  project  = var.project_id
  name     = "${local.prefix}-keyring"
  location = var.region
}

# ── Cloud SQL encryption key ──────────────────────────────────────────────────
resource "google_kms_crypto_key" "sql" {
  name            = "sql-key"
  key_ring        = google_kms_key_ring.main.id
  rotation_period = "7776000s"   # 90 days
  purpose         = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}

# ── Cloud Storage encryption key ──────────────────────────────────────────────
resource "google_kms_crypto_key" "storage" {
  name            = "storage-key"
  key_ring        = google_kms_key_ring.main.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}

# ── Secret Manager encryption key ─────────────────────────────────────────────
resource "google_kms_crypto_key" "secrets" {
  name            = "secrets-key"
  key_ring        = google_kms_key_ring.main.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = var.prevent_destroy
  }
}

# ── Grant Cloud SQL service account permission to use the SQL KMS key ─────────
data "google_project" "project" {
  project_id = var.project_id
}

resource "google_kms_crypto_key_iam_member" "sql_encrypter" {
  crypto_key_id = google_kms_crypto_key.sql.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-cloud-sql.iam.gserviceaccount.com"
}

resource "google_kms_crypto_key_iam_member" "storage_encrypter" {
  crypto_key_id = google_kms_crypto_key.storage.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.project.number}@gs-project-accounts.iam.gserviceaccount.com"
}
