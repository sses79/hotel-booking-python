variable "project_name" {
  type    = string
  default = "hotel-booking"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["eu-west-1a", "eu-west-1b"]
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.0.0/24", "10.20.1.0/24"]
}

variable "app_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.10.0/24", "10.20.11.0/24"]
}

variable "database_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.20.0/24", "10.20.21.0/24"]
}

variable "image_tag" {
  description = "Immutable container image tag, normally a Git commit SHA."
  type        = string
  default     = "bootstrap"
}

variable "ecs_desired_count" {
  description = "Start at zero until the first image is pushed in Phase 6."
  type        = number
  default     = 0

  validation {
    condition     = var.ecs_desired_count >= 0
    error_message = "ecs_desired_count must not be negative."
  }
}

variable "ecs_cpu" {
  type    = number
  default = 256
}

variable "ecs_memory" {
  type    = number
  default = 512
}

variable "rds_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "rds_allocated_storage" {
  type    = number
  default = 20
}

variable "rds_backup_retention_days" {
  type    = number
  default = 1
}

variable "rds_deletion_protection" {
  type    = bool
  default = false
}

variable "rds_skip_final_snapshot" {
  type    = bool
  default = true
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "domain_name" {
  description = "Optional fully qualified API domain name."
  type        = string
  default     = null
  nullable    = true
}

variable "route53_zone_id" {
  description = "Existing Route 53 public zone ID for domain_name."
  type        = string
  default     = null
  nullable    = true
}

variable "certificate_arn" {
  description = "Optional existing ACM certificate ARN."
  type        = string
  default     = null
  nullable    = true
}
