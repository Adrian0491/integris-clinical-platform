variable "project_id"  { type = string }
variable "region"      { type = string }
variable "environment" { type = string }
variable "app_name"    { type = string }
variable "domain_name" { type = string }
variable "alert_email" { type = string }

variable "sql_tier"               { type = string }
variable "sql_availability_type"  { type = string }
variable "sql_disk_size_gb"       { type = number }
variable "sql_backup_days"        { type = number }
variable "point_in_time_recovery" { type = bool }
variable "sql_deletion_protection" { type = bool }

variable "redis_tier"      { type = string }
variable "redis_memory_gb" { type = number }

variable "api_min_instances"    { type = number }
variable "api_max_instances"    { type = number }
variable "api_cpu"              { type = string }
variable "api_memory"           { type = string }
variable "worker_min_instances" { type = number }
variable "worker_max_instances" { type = number }
variable "worker_cpu"           { type = string }
variable "worker_memory"        { type = string }

variable "enable_cmek"        { type = bool }
variable "enable_cloud_armor" { type = bool }

# DB password — never put the real value here.
# Pass via: TF_VAR_db_password=... terraform apply
variable "db_password" {
  type      = string
  sensitive = true
  default   = ""
}
