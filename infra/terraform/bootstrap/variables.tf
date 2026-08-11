variable "project_name" {
  description = "Project name used in resource tags."
  type        = string
  default     = "hotel-booking"
}

variable "aws_region" {
  description = "AWS region that stores Terraform state."
  type        = string
  default     = "eu-west-1"
}

variable "state_bucket_name" {
  description = "Globally unique S3 bucket name for Terraform state."
  type        = string
}
