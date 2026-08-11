# AWS infrastructure

Terraform provisions the Phase 5 development environment in `eu-west-1`: a
two-AZ VPC, public ALB subnets, private ECS and RDS subnets, one NAT gateway,
ECR, ECS Fargate, encrypted RDS PostgreSQL, Secrets Manager, scoped IAM roles,
and bounded CloudWatch logs. RDS has no public route and its security group
accepts PostgreSQL only from the ECS security group.

## 1. Bootstrap remote state

Choose a globally unique bucket name and run the standalone bootstrap once:

```bash
cd infra/terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=bootstrap.tfplan
terraform apply bootstrap.tfplan
```

Copy `backend.hcl.example` to the ignored `backend.hcl` in the development
environment and set its bucket from the bootstrap output. The state bucket is
versioned, encrypted, blocks public access, denies insecure transport, uses S3
native lock files, and is protected from Terraform destruction.

## 2. Review the development plan

```bash
cd ../environments/dev
cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl
terraform fmt -check -recursive ../../
terraform validate
terraform plan -out=dev.tfplan
terraform show dev.tfplan
```

Do not apply an unreviewed plan. The defaults create an ECS service with zero
tasks because its ECR repository does not yet contain an image. Phase 6 pushes
an immutable commit-SHA tag, runs migrations as a one-off task, and raises
`ecs_desired_count` to one.

For a custom hostname, supply `domain_name` and `route53_zone_id`. Terraform
creates and DNS-validates an ACM certificate unless `certificate_arn` names an
existing certificate, redirects HTTP to HTTPS, and creates the alias record.

The database secret contains the SQLAlchemy `database_url` JSON key consumed
directly by the ECS task. Terraform state therefore contains sensitive values;
restrict access to the state bucket even though outputs are marked sensitive.

## Development cost controls

The defaults use one NAT gateway, one 0.25-vCPU/0.5-GB Fargate task once
enabled, a single-AZ `db.t4g.micro`, 20 GB gp3 storage, one-day backups, and
14-day log retention. NAT gateway and ALB hourly charges dominate a lightly
used demo. Set `ecs_desired_count = 0` when the API is not needed, but note that
the ALB, NAT gateway, and RDS still accrue hourly charges. Destroy the dev stack
when it is not in use; bootstrap state is deliberately retained.
