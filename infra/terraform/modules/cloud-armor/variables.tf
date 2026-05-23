variable "project_id"  { type = string }
variable "environment" { type = string }
variable "app_name"    { type = string }

variable "rate_limit_threshold" {
  description = "Max requests per minute per IP before throttling"
  type        = number
  default     = 1000
}

variable "enable_owasp_rules" {
  description = "Enable OWASP Core Rule Set (ModSecurity). Enable for staging/prod."
  type        = bool
  default     = true
}

variable "allowed_admin_cidrs" {
  description = "CIDRs allowed to access /api/v1/admin/* without rate limiting"
  type        = list(string)
  default     = []
}

variable "labels" {
  type    = map(string)
  default = {}
}
