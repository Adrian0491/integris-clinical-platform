variable "project_id"    { type = string }
variable "region"        { type = string }
variable "environment"   { type = string }
variable "app_name"      { type = string }
variable "vpc_network_id" { type = string }

variable "tier" {
  description = "BASIC (no replication) or STANDARD_HA (replication + failover)"
  type        = string
  default     = "STANDARD_HA"
}

variable "memory_size_gb" {
  type    = number
  default = 2
}

variable "redis_version" {
  type    = string
  default = "REDIS_7_2"
}

variable "labels" {
  type    = map(string)
  default = {}
}
