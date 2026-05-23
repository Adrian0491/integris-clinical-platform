variable "project_id"  { type = string }
variable "region"      { type = string }
variable "environment" { type = string }
variable "app_name"    { type = string }

variable "prevent_destroy" {
  description = "Prevent Terraform from destroying crypto keys (always true in prod)"
  type        = bool
  default     = false
}

variable "labels" {
  type    = map(string)
  default = {}
}
