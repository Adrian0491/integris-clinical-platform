# =============================================================================
# HTTPS Load Balancer — Google-managed SSL cert, Cloud Armor attachment,
# HTTP→HTTPS redirect, serverless NEG pointing at Cloud Run
# =============================================================================

locals {
  prefix        = "${var.app_name}-${var.environment}"
  use_armor     = var.security_policy_id != ""
}

# ── Serverless NEG (Network Endpoint Group for Cloud Run) ─────────────────────
resource "google_compute_region_network_endpoint_group" "api_neg" {
  project               = var.project_id
  name                  = "${local.prefix}-api-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = var.cloud_run_api_name
  }
}

# ── Backend service ───────────────────────────────────────────────────────────
resource "google_compute_backend_service" "api" {
  project               = var.project_id
  name                  = "${local.prefix}-api-backend"
  protocol              = "HTTPS"
  port_name             = "https"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30
  enable_cdn            = false

  # Cloud Armor
  dynamic "security_policy" {
    for_each = local.use_armor ? [var.security_policy_id] : []
    content { value = security_policy.value }
  }

  backend {
    group = google_compute_region_network_endpoint_group.api_neg.id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

# ── URL map ───────────────────────────────────────────────────────────────────
resource "google_compute_url_map" "main" {
  project         = var.project_id
  name            = "${local.prefix}-url-map"
  default_service = google_compute_backend_service.api.id
}

# ── HTTP→HTTPS redirect ────────────────────────────────────────────────────────
resource "google_compute_url_map" "http_redirect" {
  project = var.project_id
  name    = "${local.prefix}-http-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "redirect" {
  project = var.project_id
  name    = "${local.prefix}-http-proxy"
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "http" {
  project               = var.project_id
  name                  = "${local.prefix}-http-fw"
  target                = google_compute_target_http_proxy.redirect.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb_ip.address
}

# ── Google-managed SSL certificate ────────────────────────────────────────────
resource "google_compute_managed_ssl_certificate" "cert" {
  project = var.project_id
  name    = "${local.prefix}-cert"

  managed {
    domains = [var.domain_name]
  }
}

# ── HTTPS proxy ───────────────────────────────────────────────────────────────
resource "google_compute_target_https_proxy" "main" {
  project          = var.project_id
  name             = "${local.prefix}-https-proxy"
  url_map          = google_compute_url_map.main.id
  ssl_certificates = [google_compute_managed_ssl_certificate.cert.id]

  # TLS 1.3 only — HIPAA compliance
  ssl_policy = google_compute_ssl_policy.tls13.id
}

resource "google_compute_ssl_policy" "tls13" {
  project         = var.project_id
  name            = "${local.prefix}-tls13"
  min_tls_version = "TLS_1_3"
  profile         = "RESTRICTED"
}

# ── Global static IP ──────────────────────────────────────────────────────────
resource "google_compute_global_address" "lb_ip" {
  project      = var.project_id
  name         = "${local.prefix}-lb-ip"
  address_type = "EXTERNAL"
  ip_version   = "IPV4"
}

# ── HTTPS forwarding rule ──────────────────────────────────────────────────────
resource "google_compute_global_forwarding_rule" "https" {
  project               = var.project_id
  name                  = "${local.prefix}-https-fw"
  target                = google_compute_target_https_proxy.main.id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb_ip.address
}
