# =============================================================================
# Cloud Run — FastAPI (api) + Celery (worker)
# Secrets injected from Secret Manager; all traffic routed through VPC connector
# =============================================================================

locals {
  prefix      = "${var.app_name}-${var.environment}"
  api_image   = "${var.registry_url}/backend:${var.api_image_tag}"
  worker_image = "${var.registry_url}/worker:${var.api_image_tag}"

  common_env_secrets = [
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_PRIVATE_KEY",
    "JWT_PUBLIC_KEY",
    "SECRET_KEY",
    "ELASTICSEARCH_URL",
  ]
}

# ── Service Account for Cloud Run services ────────────────────────────────────
resource "google_service_account" "cloud_run" {
  project      = var.project_id
  account_id   = "${local.prefix}-run-sa"
  display_name = "Integris Cloud Run Service Account (${var.environment})"
}

# Grant Cloud Run SA access to GCS buckets
resource "google_project_iam_member" "run_sa_gcs" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Allow Cloud Run SA to use Secret Manager
resource "google_project_iam_member" "run_sa_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# ── FastAPI API service ────────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "api" {
  project  = var.project_id
  name     = "${local.prefix}-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  labels = var.labels

  template {
    service_account = google_service_account.cloud_run.email

    labels = merge(var.labels, { component = "api" })

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      name  = "api"
      image = local.api_image

      resources {
        limits = {
          cpu    = var.api_cpu
          memory = var.api_memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      ports {
        container_port = 8000
        name           = "http1"
      }

      # ── Static environment variables ───────────────────────────────────────
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "DEBUG"
        value = var.environment == "prod" ? "false" : "true"
      }
      env {
        name  = "STORAGE_BACKEND"
        value = "gcs"
      }
      env {
        name  = "GCS_BUCKET_DATASETS"
        value = var.gcs_datasets_bucket
      }
      env {
        name  = "GCS_BUCKET_REPORTS"
        value = var.gcs_reports_bucket
      }
      env {
        name  = "ENABLE_ES_INDEXING"
        value = "true"
      }

      # ── Secrets from Secret Manager ────────────────────────────────────────
      dynamic "env" {
        for_each = local.common_env_secrets
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = var.secret_ids[env.value]
              version = "latest"
            }
          }
        }
      }

      # ── Health checks ──────────────────────────────────────────────────────
      startup_probe {
        http_get { path = "/health" port = 8000 }
        initial_delay_seconds = 10
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 5
      }

      liveness_probe {
        http_get { path = "/health" port = 8000 }
        timeout_seconds   = 5
        period_seconds    = 30
        failure_threshold = 3
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_iam_member.run_sa_secrets,
    google_project_iam_member.run_sa_gcs,
  ]
}

# ── Celery worker service ──────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "worker" {
  project  = var.project_id
  name     = "${local.prefix}-worker"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"   # no public traffic

  labels = var.labels

  template {
    service_account = google_service_account.cloud_run.email

    labels = merge(var.labels, { component = "worker" })

    scaling {
      min_instance_count = var.worker_min_instances
      max_instance_count = var.worker_max_instances
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      name  = "worker"
      image = local.worker_image

      resources {
        limits = {
          cpu    = var.worker_cpu
          memory = var.worker_memory
        }
        cpu_idle = false   # worker needs CPU even when idle
      }

      ports {
        container_port = 8080   # health check port (see worker Dockerfile)
        name           = "http1"
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "STORAGE_BACKEND"
        value = "gcs"
      }
      env {
        name  = "GCS_BUCKET_DATASETS"
        value = var.gcs_datasets_bucket
      }
      env {
        name  = "GCS_BUCKET_REPORTS"
        value = var.gcs_reports_bucket
      }

      dynamic "env" {
        for_each = local.common_env_secrets
        content {
          name = env.value
          value_source {
            secret_key_ref {
              secret  = var.secret_ids[env.value]
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        http_get { path = "/health" port = 8080 }
        initial_delay_seconds = 15
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 6
      }

      liveness_probe {
        http_get { path = "/health" port = 8080 }
        timeout_seconds   = 5
        period_seconds    = 60
        failure_threshold = 3
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_iam_member.run_sa_secrets,
    google_project_iam_member.run_sa_gcs,
  ]
}

# ── Allow unauthenticated access to the API (auth handled by app) ──────────────
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
