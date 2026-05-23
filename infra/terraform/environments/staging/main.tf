# =============================================================================
# Integris Clinical Platform — staging environment
# =============================================================================

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

locals {
  labels = {
    app         = var.app_name
    environment = var.environment
    managed-by  = "terraform"
  }
  modules_path = "../../modules"
}

# ── Enable required GCP APIs ───────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "vpcaccess.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "iap.googleapis.com",
    "dns.googleapis.com",
  ])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ── Networking ────────────────────────────────────────────────────────────────
module "networking" {
  source      = "${local.modules_path}/networking"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  depends_on = [google_project_service.apis]
}

# ── KMS (only when CMEK enabled) ──────────────────────────────────────────────
module "kms" {
  count       = var.enable_cmek ? 1 : 0
  source      = "${local.modules_path}/kms"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  depends_on = [google_project_service.apis]
}

# ── Artifact Registry ─────────────────────────────────────────────────────────
module "artifact_registry" {
  source      = "${local.modules_path}/artifact-registry"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  depends_on = [google_project_service.apis]
}

# ── Cloud SQL ─────────────────────────────────────────────────────────────────
module "cloud_sql" {
  source      = "${local.modules_path}/cloud-sql"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  vpc_network_id            = module.networking.vpc_id
  private_vpc_connection_id = module.networking.private_vpc_connection_id
  kms_key_id                = var.enable_cmek ? module.kms[0].sql_key_id : ""

  tier                   = var.sql_tier
  availability_type      = var.sql_availability_type
  disk_size_gb           = var.sql_disk_size_gb
  backup_retention_days  = var.sql_backup_days
  point_in_time_recovery = var.point_in_time_recovery
  deletion_protection    = var.sql_deletion_protection
  db_password            = var.db_password

  depends_on = [module.networking]
}

# ── Memorystore Redis ─────────────────────────────────────────────────────────
module "memorystore" {
  source      = "${local.modules_path}/memorystore"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  vpc_network_id = module.networking.vpc_id
  tier           = var.redis_tier
  memory_size_gb = var.redis_memory_gb

  depends_on = [module.networking]
}

# ── Cloud Storage ─────────────────────────────────────────────────────────────
module "storage" {
  source      = "${local.modules_path}/storage"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  kms_key_id = var.enable_cmek ? module.kms[0].storage_key_id : ""

  depends_on = [google_project_service.apis]
}

# ── Secret Manager ─────────────────────────────────────────────────────────────
# The Cloud Run SA email is needed here, but Cloud Run module also needs it.
# We create the SA first with a separate resource, then reference it.
resource "google_service_account" "cloud_run" {
  project      = var.project_id
  account_id   = "${var.app_name}-${var.environment}-run-sa"
  display_name = "Integris Cloud Run SA (${var.environment})"
}

module "secrets" {
  source      = "${local.modules_path}/secrets"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  kms_key_id         = var.enable_cmek ? module.kms[0].secrets_key_id : ""
  cloud_run_sa_email = google_service_account.cloud_run.email

  # Populate computed secrets automatically
  secrets = {
    DATABASE_URL       = module.cloud_sql.database_url
    REDIS_URL          = module.memorystore.redis_url
    GCS_BUCKET_DATASETS = module.storage.datasets_bucket_name
    GCS_BUCKET_REPORTS  = module.storage.reports_bucket_name
  }

  depends_on = [module.cloud_sql, module.memorystore, module.storage]
}

# ── Cloud Armor (optional) ────────────────────────────────────────────────────
module "cloud_armor" {
  count       = var.enable_cloud_armor ? 1 : 0
  source      = "${local.modules_path}/cloud-armor"
  project_id  = var.project_id
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  enable_owasp_rules   = var.enable_cloud_armor
  rate_limit_threshold = 1000

  depends_on = [google_project_service.apis]
}

# ── Cloud Run ─────────────────────────────────────────────────────────────────
module "cloud_run" {
  source      = "${local.modules_path}/cloud-run"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  registry_url         = module.artifact_registry.registry_url
  vpc_connector_id     = module.networking.connector_id
  secret_ids           = module.secrets.secret_ids
  gcs_datasets_bucket  = module.storage.datasets_bucket_name
  gcs_reports_bucket   = module.storage.reports_bucket_name

  api_min_instances    = var.api_min_instances
  api_max_instances    = var.api_max_instances
  api_cpu              = var.api_cpu
  api_memory           = var.api_memory
  worker_min_instances = var.worker_min_instances
  worker_max_instances = var.worker_max_instances
  worker_cpu           = var.worker_cpu
  worker_memory        = var.worker_memory

  depends_on = [module.secrets, module.networking]
}

# ── Load Balancer ─────────────────────────────────────────────────────────────
module "load_balancer" {
  source      = "${local.modules_path}/load-balancer"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  domain_name             = var.domain_name
  cloud_run_api_name      = module.cloud_run.api_service_name
  cloud_run_api_location  = var.region
  security_policy_id      = var.enable_cloud_armor ? module.cloud_armor[0].policy_id : ""

  depends_on = [module.cloud_run]
}

# ── Monitoring ────────────────────────────────────────────────────────────────
module "monitoring" {
  source      = "${local.modules_path}/monitoring"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  app_name    = var.app_name
  labels      = local.labels

  api_service_name = module.cloud_run.api_service_name
  alert_email      = var.alert_email

  depends_on = [module.cloud_run]
}

# ── Outputs ────────────────────────────────────────────────────────────────────
output "lb_ip"          { value = module.load_balancer.lb_ip_address }
output "api_uri"        { value = module.cloud_run.api_uri }
output "registry_url"   { value = module.artifact_registry.registry_url }
output "sql_instance"   { value = module.cloud_sql.instance_name }
