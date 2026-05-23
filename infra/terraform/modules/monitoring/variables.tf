variable "project_id"        { type = string }
variable "region"            { type = string }
variable "environment"       { type = string }
variable "app_name"          { type = string }
variable "api_service_name"  { type = string }
variable "alert_email"       { type = string }

variable "error_rate_threshold" {
  description = "5xx error rate (0.0–1.0) that triggers an alert"
  type        = number
  default     = 0.05
}

variable "latency_p99_ms" {
  description = "P99 latency in ms that triggers an alert"
  type        = number
  default     = 5000
}

variable "labels" {
  type    = map(string)
  default = {}
}
