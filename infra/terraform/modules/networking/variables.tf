variable "project_id"   { type = string }
variable "region"       { type = string }
variable "environment"  { type = string }
variable "app_name"     { type = string }

variable "subnet_cidr" {
  type    = string
  default = "10.0.0.0/20"
}

variable "connector_cidr" {
  description = "CIDR for Serverless VPC Access connector (must be /28)"
  type        = string
  default     = "10.8.0.0/28"
}

variable "labels" {
  type    = map(string)
  default = {}
}
