output "load_balancer_url" {
  value = "${local.use_tls ? "https" : "http"}://${coalesce(var.domain_name, aws_lb.this.dns_name)}"
}

output "service_name" {
  value = aws_ecs_service.this.name
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.this.repository_url
}

output "task_execution_role_arn" {
  value = aws_iam_role.execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}
