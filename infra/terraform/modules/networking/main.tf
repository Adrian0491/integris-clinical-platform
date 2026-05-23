# =============================================================================
# Networking — VPC, subnets, NAT, Serverless VPC connector, private peering
# =============================================================================

locals {
  prefix = "${var.app_name}-${var.environment}"
}

# ── VPC ───────────────────────────────────────────────────────────────────────
resource "google_compute_network" "vpc" {
  project                 = var.project_id
  name                    = "${local.prefix}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "GLOBAL"
}

# ── Subnet ────────────────────────────────────────────────────────────────────
resource "google_compute_subnetwork" "main" {
  project                  = var.project_id
  name                     = "${local.prefix}-subnet"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = var.subnet_cidr
  private_ip_google_access = true   # reach GCP APIs without NAT

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# ── Cloud Router + NAT (for outbound internet from VMs/connectors) ────────────
resource "google_compute_router" "router" {
  project = var.project_id
  name    = "${local.prefix}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  project                            = var.project_id
  name                               = "${local.prefix}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# ── Serverless VPC Access connector (Cloud Run → VPC) ─────────────────────────
resource "google_vpc_access_connector" "connector" {
  project       = var.project_id
  name          = "${local.prefix}-connector"
  region        = var.region
  ip_cidr_range = var.connector_cidr
  network       = google_compute_network.vpc.name
  machine_type  = "e2-micro"
  min_instances = 2
  max_instances = 10
}

# ── Private Service Connection (Cloud SQL private IP) ─────────────────────────
resource "google_compute_global_address" "private_ip_range" {
  project       = var.project_id
  name          = "${local.prefix}-private-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]

  depends_on = [google_compute_global_address.private_ip_range]
}

# ── Firewall — deny all ingress by default ────────────────────────────────────
resource "google_compute_firewall" "deny_all_ingress" {
  project   = var.project_id
  name      = "${local.prefix}-deny-all-ingress"
  network   = google_compute_network.vpc.name
  direction = "INGRESS"
  priority  = 65534

  deny { protocol = "all" }
  source_ranges = ["0.0.0.0/0"]
}

# ── Firewall — allow IAP SSH for debugging ────────────────────────────────────
resource "google_compute_firewall" "allow_iap_ssh" {
  project   = var.project_id
  name      = "${local.prefix}-allow-iap-ssh"
  network   = google_compute_network.vpc.name
  direction = "INGRESS"
  priority  = 1000

  allow { protocol = "tcp"; ports = ["22"] }
  # IAP IP range
  source_ranges = ["35.235.240.0/20"]
}

# ── Firewall — allow health checks from Google LB probes ─────────────────────
resource "google_compute_firewall" "allow_health_checks" {
  project   = var.project_id
  name      = "${local.prefix}-allow-health-checks"
  network   = google_compute_network.vpc.name
  direction = "INGRESS"
  priority  = 1000

  allow { protocol = "tcp" }
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
}
