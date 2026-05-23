variable "project_id"         { type = string }
variable "region"             { type = string }
variable "environment"        { type = string }
variable "app_name"           { type = string }
variable "kms_key_id"         { type = string; default = "" }
variable "cloud_run_sa_email" { type = string }

variable "secrets" {
  description = "Map of secret name → initial value. Populate post-deploy via Secret Manager console."
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "labels" {
  type    = map(string)
  default = {}
}
