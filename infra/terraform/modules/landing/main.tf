# =============================================================================
# Terraform module: landing
# GCP Cloud Storage bucket — static website hosting for the landing page
#
# Usage (from an environment main.tf):
#   module "landing" {
#     source     = "../../modules/landing"
#     project_id = var.project_id
#     env        = var.environment
#     api_origin = "https://api.integris-clinical.com"
#     labels     = local.labels
#   }
# =============================================================================

variable "project_id" { type = string }
variable "env"        { type = string }
variable "api_origin" {
  description = "Backend API origin — used in the bucket CORS policy"
  type        = string
}
variable "labels" {
  type    = map(string)
  default = {}
}

# ── Bucket ─────────────────────────────────────────────────────────────────────
resource "google_storage_bucket" "landing" {
  name          = "integris-${var.env}-landing"
  project       = var.project_id
  location      = "US"
  storage_class = "STANDARD"
  force_destroy = var.env != "prod"

  labels = var.labels

  # Static website config
  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"   # SPA fallback
  }

  # HTTPS only — no HTTP downgrade
  uniform_bucket_level_access = true

  # CORS — allows the landing page to POST to the FastAPI backend
  cors {
    origin          = [var.api_origin]
    method          = ["GET", "POST", "OPTIONS"]
    response_header = ["Content-Type", "Authorization"]
    max_age_seconds = 3600
  }

  versioning {
    enabled = false   # Not needed for static files — deploy.sh uses rsync -d
  }
}

# ── Public read access (all objects in bucket) ─────────────────────────────────
resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# ── Outputs ────────────────────────────────────────────────────────────────────
output "bucket_name" {
  description = "GCS bucket name — pass to deploy.sh as BUCKET="
  value       = google_storage_bucket.landing.name
}

output "landing_url" {
  description = "Public website URL (no custom domain)"
  value       = "https://storage.googleapis.com/${google_storage_bucket.landing.name}/index.html"
}

output "website_endpoint" {
  description = "GCS website endpoint hostname (use as CNAME target)"
  value       = "${google_storage_bucket.landing.name}.storage.googleapis.com"
}
