output "load_balancer_url" {
  description = "Public base URL for the API."
  value       = module.service.load_balancer_url
}

output "ecs_cluster_name" {
  value = module.service.cluster_name
}

output "ecs_service_name" {
  value = module.service.service_name
}

output "ecr_repository_url" {
  value = module.service.ecr_repository_url
}

output "database_secret_arn" {
  value     = module.database.secret_arn
  sensitive = true
}

output "database_endpoint" {
  value     = module.database.endpoint
  sensitive = true
}
