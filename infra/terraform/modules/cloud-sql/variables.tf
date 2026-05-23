variable "project_id"           { type = string }
variable "region"               { type = string }
variable "environment"          { type = string }
variable "app_name"             { type = string }
variable "vpc_network_id"       { type = string }
variable "private_vpc_connection_id" { type = string }

variable "database_version" {
  type    = string
  default = "POSTGRES_16"
}

variable "tier" {
  description = "Cloud SQL machine type"
  type        = string
  default     = "db-g1-small"
}

variable "availability_type" {
  description = "REGIONAL for HA (prod), ZONAL for dev/staging"
  type        = string
  default     = "ZONAL"
}

variable "disk_size_gb" {
  type    = number
  default = 20
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "point_in_time_recovery" {
  type    = bool
  default = false
}

variable "kms_key_id" {
  description = "KMS key ID for CMEK. Empty = Google-managed key."
  type        = string
  default     = ""
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "db_name" {
  type    = string
  default = "integris"
}

variable "db_user" {
  type    = string
  default = "integris"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "labels" {
  type    = map(string)
  default = {}
}
