# =============================================================================
# Cloud Armor WAF — rate limiting, OWASP CRS, geo-blocking
# HIPAA: protects PHI endpoints from injection, XSS, and brute-force attacks
# =============================================================================

locals {
  prefix = "${var.app_name}-${var.environment}"
}

resource "google_compute_security_policy" "waf" {
  project     = var.project_id
  name        = "${local.prefix}-waf"
  description = "Integris Clinical Platform WAF policy"
  type        = "CLOUD_ARMOR"

  # ── Rule 1000: allow known admin CIDRs unconditionally ────────────────────
  dynamic "rule" {
    for_each = length(var.allowed_admin_cidrs) > 0 ? [1] : []
    content {
      action   = "allow"
      priority = 1000
      match {
        versioned_expr = "SRC_IPS_V1"
        config { src_ip_ranges = var.allowed_admin_cidrs }
      }
      description = "Allow known admin CIDRs"
    }
  }

  # ── Rule 2000: rate limit per IP ──────────────────────────────────────────
  rule {
    action   = "throttle"
    priority = 2000
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    description = "Rate limit: ${var.rate_limit_threshold} req/min per IP"
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.rate_limit_threshold
        interval_sec = 60
      }
    }
  }

  # ── Rule 3000: block SQL injection ────────────────────────────────────────
  dynamic "rule" {
    for_each = var.enable_owasp_rules ? [1] : []
    content {
      action   = "deny(403)"
      priority = 3000
      match {
        expr { expression = "evaluatePreconfiguredExpr('sqli-v33-stable')" }
      }
      description = "OWASP SQLi"
    }
  }

  # ── Rule 3100: block XSS ──────────────────────────────────────────────────
  dynamic "rule" {
    for_each = var.enable_owasp_rules ? [1] : []
    content {
      action   = "deny(403)"
      priority = 3100
      match {
        expr { expression = "evaluatePreconfiguredExpr('xss-v33-stable')" }
      }
      description = "OWASP XSS"
    }
  }

  # ── Rule 3200: block LFI ──────────────────────────────────────────────────
  dynamic "rule" {
    for_each = var.enable_owasp_rules ? [1] : []
    content {
      action   = "deny(403)"
      priority = 3200
      match {
        expr { expression = "evaluatePreconfiguredExpr('lfi-v33-stable')" }
      }
      description = "OWASP Local File Inclusion"
    }
  }

  # ── Rule 3300: block RFI ──────────────────────────────────────────────────
  dynamic "rule" {
    for_each = var.enable_owasp_rules ? [1] : []
    content {
      action   = "deny(403)"
      priority = 3300
      match {
        expr { expression = "evaluatePreconfiguredExpr('rfi-v33-stable')" }
      }
      description = "OWASP Remote File Inclusion"
    }
  }

  # ── Rule 4000: protect auth endpoints with stricter rate limit ────────────
  rule {
    action   = "throttle"
    priority = 4000
    match {
      expr {
        expression = "request.path.matches('/api/v1/auth/(login|mfa)')"
      }
    }
    description = "Brute-force protection on auth endpoints"
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = 20    # 20 login attempts per minute
        interval_sec = 60
      }
    }
  }

  # ── Rule 65535: default allow ─────────────────────────────────────────────
  rule {
    action   = "allow"
    priority = 65535
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
    description = "Default allow"
  }

  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable          = true
      rule_visibility = "STANDARD"
    }
  }
}
