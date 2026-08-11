output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = [for index in range(2) : aws_subnet.this["public-${index}"].id]
}

output "app_subnet_ids" {
  value = [for index in range(2) : aws_subnet.this["app-${index}"].id]
}

output "database_subnet_ids" {
  value = [for index in range(2) : aws_subnet.this["database-${index}"].id]
}

output "alb_security_group_id" {
  value = aws_security_group.alb.id
}

output "ecs_security_group_id" {
  value = aws_security_group.ecs.id
}

output "database_security_group_id" {
  value = aws_security_group.database.id
}
