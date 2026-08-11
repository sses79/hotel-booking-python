variable "name_prefix" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "app_subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "ecs_security_group_id" {
  type = string
}

variable "database_secret_arn" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "desired_count" {
  type = number
}

variable "cpu" {
  type = number
}

variable "memory" {
  type = number
}

variable "app_port" {
  type    = number
  default = 8000
}

variable "log_retention_days" {
  type = number
}

variable "certificate_arn" {
  description = "Optional existing ACM certificate ARN. When null, serve HTTP."
  type        = string
  default     = null
  nullable    = true
}

variable "domain_name" {
  description = "Optional DNS name to alias to the ALB."
  type        = string
  default     = null
  nullable    = true
}

variable "route53_zone_id" {
  description = "Existing Route 53 zone ID, required with domain_name."
  type        = string
  default     = null
  nullable    = true
}
