locals {
  subnet_sets = {
    public   = var.public_subnet_cidrs
    app      = var.app_subnet_cidrs
    database = var.database_subnet_cidrs
  }
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name_prefix}-igw" }
}

resource "aws_subnet" "this" {
  for_each = {
    for pair in flatten([
      for tier, cidrs in local.subnet_sets : [
        for index, cidr in cidrs : {
          key   = "${tier}-${index}"
          tier  = tier
          index = index
          cidr  = cidr
        }
      ]
    ]) : pair.key => pair
  }

  vpc_id                  = aws_vpc.this.id
  availability_zone       = var.availability_zones[each.value.index]
  cidr_block              = each.value.cidr
  map_public_ip_on_launch = each.value.tier == "public"

  tags = { Name = "${var.name_prefix}-${each.value.tier}-${each.value.index + 1}" }
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "${var.name_prefix}-nat" }

  depends_on = [aws_internet_gateway.this]
}

resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.this["public-0"].id
  tags          = { Name = "${var.name_prefix}-nat" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = { Name = "${var.name_prefix}-public" }
}

resource "aws_route_table" "app" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }

  tags = { Name = "${var.name_prefix}-app" }
}

resource "aws_route_table" "database" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name_prefix}-database" }
}

resource "aws_route_table_association" "this" {
  for_each = aws_subnet.this

  subnet_id = each.value.id
  route_table_id = (
    startswith(each.key, "public-")
    ? aws_route_table.public.id
    : startswith(each.key, "app-")
    ? aws_route_table.app.id
    : aws_route_table.database.id
  )
}

resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-alb"
  description = "Public HTTP and HTTPS access to the load balancer"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-alb" }
}

resource "aws_security_group" "ecs" {
  name        = "${var.name_prefix}-ecs"
  description = "Application traffic from the load balancer only"
  vpc_id      = aws_vpc.this.id

  ingress {
    description     = "API from ALB"
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-ecs" }
}

resource "aws_security_group" "database" {
  name        = "${var.name_prefix}-database"
  description = "PostgreSQL traffic from ECS only"
  vpc_id      = aws_vpc.this.id

  ingress {
    description     = "PostgreSQL from ECS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-database" }
}
