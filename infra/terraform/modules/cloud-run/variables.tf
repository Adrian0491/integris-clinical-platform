variable "project_id"        { type = string }
variable "region"            { type = string }
variable "environment"       { type = string }
variable "app_name"          { type = string }
variable "registry_url"      { type = string }
variable "vpc_connector_id"  { type = string }
variable "secret_ids"        { type = map(string) }
variable "gcs_datasets_bucket" { type = string }
variable "gcs_reports_bucket"  { type = string }

variable "api_image_tag" {
  type    = string
  default = "latest"
}

variable "api_cpu" {
  type    = string
  default = "1"
}

variable "api_memory" {
  type    = string
  default = "512Mi"
}

variable "api_min_instances" {
  type    = number
  default = 0
}

variable "api_max_instances" {
  type    = number
  default = 5
}

variable "worker_cpu" {
  type    = string
  default = "1"
}

variable "worker_memory" {
  type    = string
  default = "1Gi"
}

variable "worker_min_instances" {
  type    = number
  default = 0
}

variable "worker_max_instances" {
  type    = number
  default = 3
}

variable "labels" {
  type    = map(string)
  default = {}
}
