locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

module "networking" {
  source = "../../modules/networking"

  name_prefix           = local.name_prefix
  vpc_cidr              = var.vpc_cidr
  availability_zones    = var.availability_zones
  public_subnet_cidrs   = var.public_subnet_cidrs
  app_subnet_cidrs      = var.app_subnet_cidrs
  database_subnet_cidrs = var.database_subnet_cidrs
}

module "database" {
  source = "../../modules/database"

  name_prefix           = local.name_prefix
  subnet_ids            = module.networking.database_subnet_ids
  security_group_id     = module.networking.database_security_group_id
  instance_class        = var.rds_instance_class
  allocated_storage     = var.rds_allocated_storage
  backup_retention_days = var.rds_backup_retention_days
  deletion_protection   = var.rds_deletion_protection
  skip_final_snapshot   = var.rds_skip_final_snapshot
}

module "service" {
  source = "../../modules/service"

  name_prefix           = local.name_prefix
  aws_region            = var.aws_region
  vpc_id                = module.networking.vpc_id
  public_subnet_ids     = module.networking.public_subnet_ids
  app_subnet_ids        = module.networking.app_subnet_ids
  alb_security_group_id = module.networking.alb_security_group_id
  ecs_security_group_id = module.networking.ecs_security_group_id
  database_secret_arn   = module.database.secret_arn
  image_tag             = var.image_tag
  desired_count         = var.ecs_desired_count
  cpu                   = var.ecs_cpu
  memory                = var.ecs_memory
  log_retention_days    = var.log_retention_days
  domain_name           = var.domain_name
  route53_zone_id       = var.route53_zone_id
  certificate_arn       = var.certificate_arn

  depends_on = [module.database]
}
