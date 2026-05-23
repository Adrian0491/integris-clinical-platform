# =============================================================================
# Cloud Operations Suite — alerting, uptime checks, log metrics
# Covers: API errors, latency, Cloud SQL, Redis, failed auth, validation jobs
# =============================================================================

locals {
  prefix = "${var.app_name}-${var.environment}"
}

# ── Notification channel (email) ──────────────────────────────────────────────
resource "google_monitoring_notification_channel" "email" {
  project      = var.project_id
  display_name = "Integris ${var.environment} Alerts"
  type         = "email"
  labels       = { email_address = var.alert_email }
}

# ── Uptime check ──────────────────────────────────────────────────────────────
resource "google_monitoring_uptime_check_config" "api_health" {
  project      = var.project_id
  display_name = "${local.prefix}-api-health"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true
    request_method = "GET"
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = "${var.app_name}-${var.environment}.run.app"
    }
  }

  content_matchers {
    content = "\"status\": \"ok\""
    matcher = "CONTAINS_STRING"
  }
}

# ── Alert: API downtime ────────────────────────────────────────────────────────
resource "google_monitoring_alert_policy" "uptime" {
  project      = var.project_id
  display_name = "${local.prefix} API Downtime"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "API health check failing"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" resource.type=\"uptime_url\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "120s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_TRUE"
        group_by_fields    = ["resource.label.host"]
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  alert_strategy {
    notification_rate_limit { period = "3600s" }
  }
}

# ── Alert: High 5xx error rate ─────────────────────────────────────────────────
resource "google_monitoring_alert_policy" "error_rate" {
  project      = var.project_id
  display_name = "${local.prefix} High 5xx Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run 5xx error rate > ${var.error_rate_threshold * 100}%"
    condition_threshold {
      filter = join(" AND ", [
        "resource.type=\"cloud_run_revision\"",
        "metric.type=\"run.googleapis.com/request_count\"",
        "metric.labels.response_code_class=\"5xx\"",
        "resource.labels.service_name=\"${var.api_service_name}\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = var.error_rate_threshold
      duration        = "300s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

# ── Alert: High P99 latency ────────────────────────────────────────────────────
resource "google_monitoring_alert_policy" "latency" {
  project      = var.project_id
  display_name = "${local.prefix} High API Latency"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run P99 latency > ${var.latency_p99_ms}ms"
    condition_threshold {
      filter = join(" AND ", [
        "resource.type=\"cloud_run_revision\"",
        "metric.type=\"run.googleapis.com/request_latencies\"",
        "resource.labels.service_name=\"${var.api_service_name}\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = var.latency_p99_ms
      duration        = "300s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

# ── Alert: Cloud SQL CPU > 80% ─────────────────────────────────────────────────
resource "google_monitoring_alert_policy" "sql_cpu" {
  project      = var.project_id
  display_name = "${local.prefix} Cloud SQL High CPU"
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL CPU utilization > 80%"
    condition_threshold {
      filter          = "resource.type=\"cloudsql_database\" metric.type=\"cloudsql.googleapis.com/database/cpu/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

# ── Alert: Cloud SQL disk > 85% ───────────────────────────────────────────────
resource "google_monitoring_alert_policy" "sql_disk" {
  project      = var.project_id
  display_name = "${local.prefix} Cloud SQL Disk Usage"
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL disk usage > 85%"
    condition_threshold {
      filter          = "resource.type=\"cloudsql_database\" metric.type=\"cloudsql.googleapis.com/database/disk/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.85
      duration        = "600s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

# ── Alert: Redis memory > 80% ─────────────────────────────────────────────────
resource "google_monitoring_alert_policy" "redis_memory" {
  project      = var.project_id
  display_name = "${local.prefix} Redis Memory Usage"
  combiner     = "OR"

  conditions {
    display_name = "Redis memory ratio > 80%"
    condition_threshold {
      filter          = "resource.type=\"redis_instance\" metric.type=\"redis.googleapis.com/stats/memory/usage_ratio\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

# ── Log metric: failed login attempts ─────────────────────────────────────────
resource "google_logging_metric" "failed_logins" {
  project     = var.project_id
  name        = "${local.prefix}-failed-logins"
  description = "Count of failed login attempts (brute-force detection)"
  filter      = "resource.type=\"cloud_run_revision\" jsonPayload.message=\"Login failed\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    display_name = "Failed Login Attempts"
  }
}

# ── Alert: suspicious login spike ─────────────────────────────────────────────
resource "google_monitoring_alert_policy" "login_spike" {
  project      = var.project_id
  display_name = "${local.prefix} Suspicious Login Activity"
  combiner     = "OR"

  conditions {
    display_name = "More than 50 failed logins in 5 minutes"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.failed_logins.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 50
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}
