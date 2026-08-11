output "state_bucket_name" {
  description = "Bucket to configure as the environment S3 backend."
  value       = aws_s3_bucket.terraform_state.id
}

output "backend_configuration" {
  description = "Backend settings to copy into an environment backend config."
  value = {
    bucket       = aws_s3_bucket.terraform_state.id
    key          = "environments/dev/terraform.tfstate"
    region       = var.aws_region
    encrypt      = true
    use_lockfile = true
  }
}
