resource "random_password" "master" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-database"
  subnet_ids = var.subnet_ids
  tags       = { Name = "${var.name_prefix}-database" }
}

resource "aws_db_instance" "this" {
  identifier = "${var.name_prefix}-postgres"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  db_name  = var.database_name
  username = var.master_username
  password = random_password.master.result
  port     = 5432

  allocated_storage     = var.allocated_storage
  max_allocated_storage = max(var.allocated_storage, 100)
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  multi_az               = var.multi_az

  backup_retention_period = var.backup_retention_days
  copy_tags_to_snapshot   = true
  deletion_protection     = var.deletion_protection
  skip_final_snapshot     = var.skip_final_snapshot
  final_snapshot_identifier = (
    var.skip_final_snapshot ? null : "${var.name_prefix}-final"
  )

  auto_minor_version_upgrade   = true
  maintenance_window           = "sun:03:00-sun:04:00"
  backup_window                = "01:00-02:00"
  performance_insights_enabled = false

  tags = { Name = "${var.name_prefix}-postgres" }
}

resource "aws_secretsmanager_secret" "database" {
  name                    = "${var.name_prefix}/database"
  recovery_window_in_days = var.deletion_protection ? 30 : 0

  tags = { Name = "${var.name_prefix}-database" }
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id
  secret_string = jsonencode({
    username     = var.master_username
    password     = random_password.master.result
    host         = aws_db_instance.this.address
    port         = aws_db_instance.this.port
    database     = var.database_name
    database_url = "postgresql+asyncpg://${var.master_username}:${urlencode(random_password.master.result)}@${aws_db_instance.this.address}:${aws_db_instance.this.port}/${var.database_name}"
  })
}
