# Hotel Booking API Implementation Plan

## Goal

Build a small, production-shaped hotel room booking API with Python, FastAPI,
SQLAlchemy, and PostgreSQL. The project should be easy to run locally with
Docker Compose, easy to inspect through OpenAPI, covered by focused automated
tests, and deployable to AWS using Terraform.

The delivery priority is correctness of booking and availability rules. Keep
the design clear and practical; this is a demo API, not a large platform.

## Scope And Assumptions

The first release includes:

- Find a hotel by name.
- Find rooms available for a date range and guest count.
- Create a room booking.
- Look up a booking by its public reference.
- Seed predictable demo data and reset local/test data.
- Health and readiness endpoints.
- Interactive OpenAPI documentation.
- Local PostgreSQL and API containers through Docker Compose.
- Repeatable AWS infrastructure and deployment through Terraform.

The first release does not include a frontend, payments, customer accounts, or
authentication, including email or magic-link authentication. These are
confirmed as outside the MVP and can be added later without changing the
booking core. Admin seed/reset endpoints must be disabled outside local and test
environments.

## Technology Choices

- Python 3.14 using the standard GIL-enabled build.
- FastAPI for HTTP routing, validation, dependency injection, and OpenAPI.
- Pydantic v2 plus `pydantic-settings` for API schemas and configuration.
- SQLAlchemy 2.x using its async API.
- `asyncpg` as the PostgreSQL application driver.
- Alembic for database migrations.
- PostgreSQL 16 locally and Amazon RDS for PostgreSQL in AWS.
- Pytest, pytest-asyncio, HTTPX, and Testcontainers for tests.
- Ruff for linting and formatting; mypy for static type checks.
- Docker and Docker Compose for local development.
- Terraform for AWS infrastructure.

Use `uv` for dependency management, virtual environments, command execution,
and lock-file generation. Pin direct dependencies and commit `uv.lock` for
reproducible environments.

Release the repository under the MIT License and commit the standard license
text as `LICENSE` during Phase 1.

## Project Structure

Use one application package with feature-focused modules:

```text
.
├── app/
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── admin.py
│   │       ├── bookings.py
│   │       ├── health.py
│   │       └── hotels.py
│   ├── core/
│   │   ├── config.py
│   │   ├── errors.py
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py
│   │   ├── models.py
│   │   └── session.py
│   ├── repositories/
│   │   ├── bookings.py
│   │   └── hotels.py
│   ├── schemas/
│   │   ├── bookings.py
│   │   └── hotels.py
│   ├── services/
│   │   ├── booking.py
│   │   └── seed.py
│   └── main.py
├── migrations/
├── tests/
│   ├── unit/
│   └── integration/
├── infra/
│   ├── local/
│   │   └── compose.yaml
│   └── terraform/
│       ├── bootstrap/
│       ├── environments/
│       │   └── dev/
│       └── modules/
│           ├── database/
│           ├── networking/
│           └── service/
├── scripts/
├── docs/
├── Dockerfile
├── .env.example
├── alembic.ini
├── pyproject.toml
└── README.md
```

Responsibilities:

- `api/routes`: HTTP concerns only; validate input, invoke a service, and map
  known outcomes to responses.
- `schemas`: Pydantic request and response contracts. Do not return ORM models
  directly.
- `services`: booking, availability, seed, and reset use cases.
- `repositories`: focused SQLAlchemy queries and persistence operations.
- `db`: ORM models, engine, sessions, and transaction primitives.
- `core`: environment settings, logging, and shared application errors.
- `migrations`: the only source of truth for database schema changes.
- `infra`: local containers and AWS Terraform, kept separate from app code.

Avoid adding generic base repositories, a dependency-injection framework, or
multiple application layers until the project has a real need for them.

## Runtime Architecture

```text
Local
  Client -> FastAPI container -> PostgreSQL container

AWS
  Client -> Application Load Balancer -> ECS Fargate service
                                      -> RDS PostgreSQL
```

FastAPI is served by Uvicorn. The container exposes one HTTP port, handles
SIGTERM cleanly, and runs as a non-root user. The application is stateless, so
ECS can replace or scale tasks without moving application data.

## Domain Model

Core entities:

```text
Hotel
  id: UUID
  name: string
  created_at: timestamptz

Room
  id: UUID
  hotel_id: UUID
  room_number: string
  room_type: single | double | deluxe
  capacity: integer

Booking
  id: UUID
  reference: string
  hotel_id: UUID
  room_id: UUID
  guest_name: string
  guest_count: integer
  check_in_date: date
  check_out_date: date
  created_at: timestamptz
```

Database constraints and indexes:

- Unique hotel name for the demo dataset.
- Unique `(hotel_id, room_number)`.
- Unique booking reference.
- Positive room capacity and guest count.
- `check_in_date < check_out_date`.
- Foreign keys from rooms to hotels and bookings to hotels/rooms.
- Index booking date lookups by room.
- Ensure a booking's room belongs to the selected hotel in application logic;
  consider a composite database constraint if this invariant becomes risky.

Use UUID primary keys generated by the application. Store timestamps in UTC
and expose ISO 8601 values.

## Booking Rules

- A hotel has single, double, and deluxe rooms.
- A room cannot be double booked for any occupied night.
- Guests remain in one room for the entire stay.
- Guest count cannot exceed room capacity.
- Booking references are unique and difficult to guess.
- Check-in must be today or later.
- Check-out must be after check-in.

Use half-open date ranges:

```text
[check_in_date, check_out_date)
```

Two bookings overlap when:

```python
existing.check_in_date < requested.check_out_date
and requested.check_in_date < existing.check_out_date
```

This permits a new guest to check in on the date the previous guest checks
out.

### Concurrency Safety

Availability and booking creation must not rely on an unprotected "check then
insert" sequence.

1. Begin a database transaction.
2. Select suitable rooms in stable order: smallest capacity, room type, then
   room number.
3. Lock candidate room rows with `SELECT ... FOR UPDATE SKIP LOCKED`.
4. Exclude rooms with an overlapping booking.
5. Insert the booking and commit.
6. Return a conflict response if no suitable room remains.

As a final database guard, add PostgreSQL's `btree_gist` extension and an
exclusion constraint preventing overlapping `daterange` values for the same
room. Map an exclusion violation to `409 Conflict`. This protects correctness
even if a future code path omits the expected lock.

## API Surface

Use an `/api/v1` prefix so future incompatible changes can coexist.

```text
GET  /api/v1/hotels?name=...
GET  /api/v1/hotels/{hotel_id}/rooms/available
POST /api/v1/bookings
GET  /api/v1/bookings/{reference}
POST /api/v1/admin/seed
POST /api/v1/admin/reset
GET  /health/live
GET  /health/ready
GET  /docs
GET  /openapi.json
```

Availability query parameters:

```text
check_in=2026-09-01
check_out=2026-09-03
guests=2
room_type=double   # optional
```

Example booking request:

```json
{
  "hotel_id": "00000000-0000-0000-0000-000000000001",
  "guest_name": "Ada Lovelace",
  "guest_count": 2,
  "check_in_date": "2026-09-01",
  "check_out_date": "2026-09-03",
  "room_type": "double"
}
```

Return `201 Created` with a `Location` header after booking. Use consistent
problem responses with fields such as `code`, `message`, and `details`.
Expected status codes include `400` for malformed requests, `404` for unknown
resources, `409` when no room is available or a concurrent booking wins, and
`422` for FastAPI schema validation errors.

## Seed And Reset

`POST /api/v1/admin/seed` first resets data and then creates a deterministic
hotel:

```text
Grand Plaza Hotel
  101 single capacity 1
  102 single capacity 1
  201 double capacity 2
  202 double capacity 2
  301 deluxe capacity 4
  302 deluxe capacity 4
```

Do not seed bookings. Reviewers should exercise the real booking endpoint.
Seed returns the stable hotel ID and number of rooms created.

Seed/reset routes are registered only when `APP_ENV` is `local` or `test`.
Production data changes use migrations and purpose-built operational tasks, not
public admin endpoints.

## Configuration

Settings are read from environment variables and validated at startup:

```text
APP_ENV
LOG_LEVEL
DATABASE_URL
DB_POOL_SIZE
DB_MAX_OVERFLOW
AWS_REGION
```

`.env.example` contains safe local defaults only. Never commit `.env`, AWS
credentials, database passwords, Terraform state, or `terraform.tfvars` with
secrets. Local Compose may construct `DATABASE_URL` from its local-only
PostgreSQL values. In AWS, inject the RDS connection details and password from
AWS Secrets Manager into the ECS task.

## Local Development

Docker Compose runs:

- `api`: FastAPI with source mounted for reload in development.
- `db`: PostgreSQL 16 with a named volume and health check.
- Optional one-shot `migrate` profile for `alembic upgrade head`.

Expected commands:

```bash
docker compose --env-file .env -f infra/local/compose.yaml up --build
docker compose --env-file .env -f infra/local/compose.yaml run --rm migrate
docker compose --env-file .env -f infra/local/compose.yaml down
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

The database health check must complete before migrations or the API start.
Document how to reset the named development volume when a fully clean database
is needed; do not make ordinary shutdown delete developer data.

## Testing Strategy

### Unit Tests

Keep fast tests around pure booking decisions:

- Invalid and valid date ranges.
- Half-open overlap behavior.
- Back-to-back bookings.
- Capacity filtering.
- Optional room type filtering.
- Deterministic smallest-suitable-room ordering.
- Public booking reference format.

### Integration Tests

Use a real disposable PostgreSQL container, apply Alembic migrations, and test
through HTTPX against the FastAPI ASGI app:

- Health and readiness.
- Hotel name lookup.
- Seed is repeatable and reset removes data.
- Availability before and after bookings.
- Booking creation and reference lookup.
- No availability when all suitable rooms overlap.
- A smaller room is never assigned beyond capacity.
- Concurrent requests cannot reserve the same final room.
- The PostgreSQL exclusion constraint rejects direct overlapping inserts.
- Production configuration does not expose seed/reset routes.

Do not replace relational tests with SQLite: its locking, range constraints,
and SQL behavior do not match PostgreSQL closely enough for the risky paths.

## AWS Deployment Plan

Follow the AWS conventions from the existing `aws-auth` example: use AWS CLI
credentials outside the repository, manage infrastructure with Terraform, and
default the development region to `eu-west-1`. Domain values remain Terraform
inputs; an existing Route 53 zone may be referenced if desired rather than
created or transferred by this project.

### AWS Resources

- VPC spanning two Availability Zones.
- Public subnets for an internet-facing Application Load Balancer.
- Private application subnets for ECS Fargate tasks.
- Private database subnets for RDS PostgreSQL.
- NAT egress for private ECS tasks; use one NAT gateway in the demo environment
  to control cost, and one per Availability Zone for production resilience.
- ECR repository with image scanning and lifecycle rules.
- ECS cluster, task definition, and Fargate service.
- Application Load Balancer, target group, and health check.
- RDS PostgreSQL with encrypted storage, automated backups, and deletion
  protection configurable by environment.
- Secrets Manager secret for database credentials.
- Least-privilege task execution and application IAM roles.
- CloudWatch log group with a bounded retention period.
- Optional ACM certificate and Route 53 alias record for HTTPS.

Security groups allow only:

```text
Internet -> ALB: 443 (and optional 80 redirect)
ALB -> ECS: application port
ECS -> RDS: 5432
```

RDS must not be publicly accessible. ECS tasks should not accept traffic except
from the ALB security group.

### Terraform Layout And State

Terraform modules represent stable resource groups, while
`infra/terraform/environments/dev` composes them. Pin Terraform and provider
versions and commit `.terraform.lock.hcl`.

Bootstrap remote state separately:

- An encrypted, versioned S3 bucket.
- S3 native state locking (`use_lockfile = true`) when supported by the pinned
  Terraform version.
- Public access blocked.
- A distinct state key per environment.

Terraform inputs include project name, environment, region, VPC CIDRs, domain
settings, container image tag, ECS sizing, RDS instance class, and backup
retention. Outputs include the load balancer URL, service name, ECR repository,
and database secret ARN. Sensitive outputs must be marked sensitive.

### Build And Release

1. Run lint, type checks, unit tests, and PostgreSQL integration tests.
2. Build the same multi-stage Docker image used locally.
3. Scan the image and push it to ECR using an immutable Git commit SHA tag.
4. Run `terraform fmt -check`, `validate`, and `plan`.
5. Apply infrastructure changes after review.
6. Run `alembic upgrade head` as a one-off ECS task using the deployed image.
7. Update the ECS service to the immutable image tag.
8. Wait for load balancer health checks and run a smoke test.

Do not run migrations independently from every web task at startup; multiple
tasks could race. A failed migration stops the deployment before application
traffic moves to the new revision.

For CI/CD, prefer GitHub Actions OpenID Connect to assume a narrowly scoped AWS
deployment role. Do not store long-lived AWS access keys in repository secrets.

## Observability And Operations

- Emit structured JSON logs to stdout with request ID, route, status, latency,
  and error code; never log guest data or secrets unnecessarily.
- Accept or generate an `X-Request-ID` and return it to callers.
- ALB uses `/health/live`; `/health/ready` checks database connectivity with a
  short timeout.
- Configure ECS deployment rollback/circuit breaker.
- Set CloudWatch alarms for unhealthy targets, elevated 5xx responses, ECS task
  failures, RDS storage, CPU, connections, and backup failures.
- Keep log retention finite in the demo environment.
- Document database restore and secret rotation procedures before calling the
  deployment production-ready.

## Implementation Phases

### Phase 1: Project Foundation

- Create the Python package, settings, FastAPI app factory, health endpoints,
  linting, typing, and test configuration.
- Configure `uv` and commit the generated `uv.lock`.
- Add Dockerfile, local Compose, `.env.example`, and developer commands.
- Add repository essentials: `README.md`, MIT `LICENSE`, `.gitignore`,
  `.dockerignore`, and `.editorconfig`.
- Add an initial GitHub Actions workflow for Ruff, formatting, mypy, and tests.
  Once the workflow succeeds on `dev`, require its stable check on protected
  `main`.

Exit criterion: the API and PostgreSQL start locally; local checks pass; CI
passes on `dev`; and the documented setup works from a clean checkout.

### Phase 2: Database And Seed Data

- Add SQLAlchemy models, async sessions, Alembic, initial migration, PostgreSQL
  constraints, and seed/reset services.

Exit criterion: migrations work on a fresh database and seed is repeatable.

### Phase 3: Search And Availability

- Implement hotel lookup, availability queries, schemas, error mapping, and
  unit/integration coverage.

Exit criterion: OpenAPI can find the seeded hotel and suitable free rooms.

### Phase 4: Booking

- Implement transactional room selection, reference generation, the exclusion
  constraint, booking lookup, and concurrency tests.

Exit criterion: normal, back-to-back, capacity, and concurrent booking cases
all behave correctly.

### Phase 5: AWS Infrastructure

- Add Terraform state bootstrap, networking, ECR, ECS/ALB, RDS, secrets, IAM,
  logs, and optional DNS/TLS.
- Produce and review a Terraform plan for `eu-west-1` before any apply.

Exit criterion: Terraform validates and a reviewed development environment can
be created without manual console configuration.

### Phase 6: Deployment And Documentation (Deferred / Optional)

This phase is not required to complete the local-first demo. The repository is
considered feature-complete after Phase 5; continue with deployment only when a
hosted environment is specifically needed and its recurring AWS cost has been
reviewed.

- Add image publishing, one-off migration, ECS rollout, smoke-test workflow,
  operational notes, architecture diagram, and complete README.

Exit criterion: a new contributor can run locally, test, deploy, verify, and
troubleshoot the API using documented commands.

## Definition Of Done

- All API behavior is documented in generated OpenAPI and the README.
- Local startup requires only the documented prerequisites and commands.
- Alembic can build a fresh PostgreSQL schema from zero.
- Unit and real-PostgreSQL integration tests pass.
- Concurrent booking of the final room produces one success and one conflict.
- Ruff, formatting, and mypy checks pass.
- The image runs as non-root and contains no secrets.
- Terraform is formatted, validated, and has a reviewed plan.
- AWS uses private RDS networking, encrypted data, least-privilege IAM, bounded
  logs, and immutable image tags.
- Seed/reset cannot be reached in production.
- No credentials, secrets, local environment files, state files, or customer
  data are committed.
