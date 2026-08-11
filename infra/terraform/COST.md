# Development cost estimate

Estimated on 2026-08-11 for `eu-west-1`, using 730 hours per month and AWS
on-demand list prices in USD, excluding tax and free-tier credits.

| Component | Assumption | Monthly USD |
| --- | --- | ---: |
| NAT gateway | 1 × $0.048/hour | $35.04 |
| Application Load Balancer | 1 × $0.0252/hour | $18.40 |
| Public IPv4 | 2 ALB addresses + 1 NAT EIP × $0.005/hour | $10.95 |
| RDS PostgreSQL compute | Single-AZ `db.t4g.micro` × $0.017/hour | $12.41 |
| RDS gp3 storage | 20 GB × $0.127/GB-month | $2.54 |
| Fargate task | 0.25 vCPU + 0.5 GB, one task continuously | $9.01 |
| Secrets Manager | 1 secret | $0.40 |
| Light usage allowance | Logs/metrics, ALB LCUs, NAT data, ECR and S3 | $6.00 |
| **Expected deployed total** | Low-traffic demo | **about $95/month** |

The Phase 5 default has `ecs_desired_count = 0` until an image is pushed, so
its expected idle cost is about **$82–86/month**. Running one task continuously
raises that to about **$91 before observability and traffic**, or roughly
**$95/month** for a lightly used demo.

Variable charges are not capped by this estimate. NAT processing is $0.048/GB;
ALB capacity is $0.008/LCU-hour; internet and cross-AZ transfer, log ingestion,
RDS burst CPU credits, snapshots beyond the free backup allocation, and a
database storage autoscale above 20 GB cost extra. The configured RDS maximum
is 100 GB, which would add about $10.16/month if fully used.

Current rates should be rechecked before apply:

- [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/)
- [Elastic Load Balancing pricing](https://aws.amazon.com/elasticloadbalancing/pricing/)
- [Amazon VPC pricing](https://aws.amazon.com/vpc/pricing/)
- [Amazon RDS for PostgreSQL pricing](https://aws.amazon.com/rds/postgresql/pricing/)

The NAT gateway and ALB account for most of the idle bill. A cheaper
non-production variant could place a single task in a public subnet and remove
both, but that is a different security and availability posture from the Phase
5 architecture.
