variable "project_id"          { type = string }
variable "region"              { type = string }
variable "environment"         { type = string }
variable "app_name"            { type = string }
variable "domain_name"         { type = string }
variable "cloud_run_api_name"  { type = string }
variable "cloud_run_api_location" { type = string }
variable "security_policy_id" {
  type    = string
  default = ""
}

variable "labels" {
  type    = map(string)
  default = {}
}
