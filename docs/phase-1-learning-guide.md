# Phase 1 Learning Guide

Phase 1 establishes the smallest foundation that can run the API, reach a real
PostgreSQL database, and prove the same expectations locally and in CI. It does
not implement hotel or booking behavior yet. Its value is the set of boundaries
that Phase 2 can build on without inventing startup, configuration, dependency,
or test conventions again.

## The 80/20 View

Five ideas explain most of Phase 1:

1. `create_app()` is the composition root: it assembles settings, logging, the
   database engine, lifecycle cleanup, and routes.
2. Configuration is validated input, not scattered environment lookups.
3. Liveness answers "is the process serving?" while readiness answers "can it
   use PostgreSQL?"
4. `pyproject.toml`, `uv.lock`, and the Docker stages make the environment
   reproducible across a laptop, a container, and CI.
5. Tests gain confidence at the cheapest useful boundary, then CI repeats the
   complete check with a real PostgreSQL service.

These ideas are more important than memorizing the current file tree. New
features should plug into these boundaries instead of creating parallel ways to
configure, start, or test the application.

## 1. The Application Factory Owns Assembly

The central function is `create_app()` in
[`app/main.py`](../app/main.py). It performs the application-wide wiring:

```text
Settings
  + logging configuration
  + async SQLAlchemy engine
  + FastAPI lifespan
  + health router
  -> FastAPI application
```

At module import time, `app = create_app()` creates the ASGI object used by
Uvicorn. This is why both the local command and container command can point to
the same entrypoint:

```bash
uv run uvicorn app.main:app --reload
```

The factory also makes tests independent. A test can pass an explicit
`Settings(app_env="test")` rather than modifying global process configuration.
The optional `db_engine` argument is an injection seam for a controlled engine
when a future test needs one.

The FastAPI lifespan disposes `application.state.db_engine` during shutdown.
Engine creation does not itself prove that PostgreSQL is reachable; the first
connection is opened when a route or service needs one. This allows the process
to start independently from a database query while still cleaning up its
connection pool correctly.

Transferable lesson: keep application-wide construction in one visible place.
When Phase 2 adds sessions and repositories, wire their shared infrastructure
through this root instead of creating engines inside route handlers.

## 2. Configuration Is A Validated Runtime Contract

[`app/core/config.py`](../app/core/config.py) defines every current application
setting with Pydantic Settings. The types express accepted values and reject
bad configuration early:

- `app_env` is one of `local`, `test`, `dev`, or `prod`.
- `log_level` is restricted to known logging levels.
- `db_pool_size` must be at least one.
- `db_max_overflow` cannot be negative.

`get_settings()` is cached, so normal application startup builds the settings
once per process. Tests avoid that shared cache by constructing `Settings`
directly.

The same names cross the local boundary in
[`infra/local/compose.yaml`](../infra/local/compose.yaml). Compose reads values
from `.env`, supplies local fallbacks, and changes the database hostname from
`localhost` to the Compose service name `db`. In particular,
`APP_ENV: ${APP_ENV:-local}` preserves an explicit operator choice instead of
silently forcing local mode.

[`app/core/logging.py`](../app/core/logging.py) consumes `log_level`, while
[`app/db/session.py`](../app/db/session.py) consumes the database URL and pool
settings. Route modules do not call `os.getenv()` themselves.

Transferable lesson: read external configuration at the edge, validate it once,
then pass typed settings to the code that owns each resource.

## 3. Liveness And Readiness Answer Different Questions

[`app/api/routes/health.py`](../app/api/routes/health.py) deliberately exposes
two health signals:

```text
GET /health/live
  -> FastAPI handler runs
  -> 200 {"status": "alive"}

GET /health/ready
  -> obtain engine from application.state
  -> open pooled PostgreSQL connection
  -> execute SELECT 1
     -> success: 200 {"status": "ready"}
     -> OSError/SQLAlchemyError: 503 {"status": "not_ready"}
```

Liveness does not touch the database. A database outage should not claim that
the API process is dead and trigger endless restarts. Readiness does touch the
database, so a load balancer can stop routing business traffic to an instance
that cannot satisfy database-backed requests.

The readiness query proves connectivity, authentication, and the ability to
execute SQL. It does not prove that migrations are current or booking tables
exist; those checks belong to Phase 2 and deployment operations.

The `HealthResponse` Pydantic model constrains response values and feeds the
generated OpenAPI contract. The explicit `503` response declaration documents
the unhealthy readiness outcome even though the successful and unsuccessful
responses use different FastAPI response paths.

Transferable lesson: name operational endpoints after the decision they enable.
"The process exists" and "the instance can receive traffic" are distinct
decisions.

## 4. Reproducibility Comes From Intent Plus A Lock

[`pyproject.toml`](../pyproject.toml) records dependency intent and development
policy:

- Python must be 3.14.
- Runtime packages include FastAPI, Pydantic Settings, SQLAlchemy, asyncpg, and
  Uvicorn.
- The development group includes HTTPX, mypy, pytest, pytest-asyncio, and Ruff.
- Ruff and mypy both analyze the project as Python 3.14.

[`uv.lock`](../uv.lock) records the exact resolved package graph. The distinction
is useful:

```text
pyproject.toml = versions the project permits
uv.lock        = versions this revision installs
```

`uv sync --frozen --all-groups` refuses to rewrite the lock file and installs
runtime plus development dependencies. That makes a stale lock visible instead
of quietly changing the environment during CI.

The multi-stage [`Dockerfile`](../Dockerfile) uses the same lock but installs
only runtime dependencies. The final image receives the virtual environment and
application code, not Ruff, pytest, mypy, or the `uv` binary. It runs as the
unprivileged `app` user rather than root.

Compose adds development behavior around that production-shaped image:

- PostgreSQL has a persistent named volume and a real health check.
- The API waits for the database to become healthy before starting.
- Source is mounted read-only and Uvicorn reload is enabled.
- Ordinary `down` preserves database data; `down --volumes` is an explicit
  destructive reset.

Transferable lesson: declare flexible compatibility in project metadata, lock
the exact graph for repeatability, and keep development-only tools out of the
runtime image.

## 5. Tests Prove Boundaries, Not Just Functions

[`tests/unit/test_health.py`](../tests/unit/test_health.py) sends requests
directly into the ASGI application with HTTPX. It proves that:

- the application factory can construct a test instance;
- `/health/live` returns the expected status and body;
- FastAPI generates an OpenAPI document containing both health routes; and
- response status is checked before the test interprets response JSON.

These tests do not require a listening TCP port or a running database, so they
are fast and isolate the HTTP/application boundary.

[`tests/integration/test_readiness.py`](../tests/integration/test_readiness.py)
crosses the database boundary. It uses `TEST_DATABASE_URL` to build a real
asyncpg-backed SQLAlchemy engine and calls `/health/ready`. Without that
variable, the test is intentionally skipped rather than accidentally connecting
to a developer database.

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) supplies a disposable
PostgreSQL service and `TEST_DATABASE_URL`, so the integration test is not
skipped in CI. The `quality` job then runs locked installation, linting,
formatting, strict typing, and all tests. That check is the stable protection
boundary for `main`.

Phase 1 tests do not yet prove:

- ORM models, migrations, or schema correctness;
- seed/reset behavior;
- hotel search, availability, or bookings;
- transaction and concurrent-booking guarantees;
- the readiness `503` branch; or
- a Docker image build inside CI.

Those are real gaps, not test failures. They mark where later phases must add
evidence.

Transferable lesson: choose the cheapest test that crosses the boundary at risk.
Use an in-process ASGI test for routing, but use real PostgreSQL for behavior
that depends on PostgreSQL.

## Execution Flow

### Startup

```text
Uvicorn imports app.main:app
  -> create_app()
     -> get_settings() reads defaults, .env, and environment variables
     -> configure_logging()
     -> create_engine() builds the async connection pool
     -> FastAPI stores settings and engine on application.state
     -> health router is registered
  -> server begins accepting requests
  -> shutdown triggers engine.dispose()
```

### Local Container Startup

```text
docker compose up --build
  -> PostgreSQL starts
  -> pg_isready health check succeeds
  -> API container starts Uvicorn with reload
  -> /health/live proves HTTP process health
  -> /health/ready proves PostgreSQL connectivity
```

### CI

```text
push to dev or pull request
  -> PostgreSQL service becomes healthy
  -> uv installs uv.lock exactly
  -> Ruff lint
  -> Ruff format check
  -> mypy strict check
  -> pytest, including PostgreSQL readiness integration
  -> required quality result
```

## What The Tests Prove

| Boundary | Evidence | Confidence gained | Important limit |
| --- | --- | --- | --- |
| Python import and construction | Unit tests create the app | Wiring imports and constructs successfully | No production server socket |
| HTTP and OpenAPI | HTTPX calls ASGI routes | Route, status, body, and schema registration work | No reverse proxy or TLS |
| PostgreSQL readiness | Integration test executes through asyncpg | Real connection and `SELECT 1` work | No application schema yet |
| Static correctness | Ruff and strict mypy | Style, common defects, and typed interfaces are checked | Static analysis cannot prove runtime business rules |
| Reproducible CI | Frozen `uv.lock` installation | CI uses a known package graph | Container build is not currently a CI step |

## Try It

Install exactly the locked runtime and development environment:

```bash
uv sync --frozen --all-groups
uv run python -c "import fastapi; print(fastapi.__version__)"
```

Run the inexpensive checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Run the complete local stack:

```bash
test -f .env || cp .env.example .env
docker compose --env-file .env -f infra/local/compose.yaml up --build
```

Then inspect <http://localhost:8000/docs>,
<http://localhost:8000/health/live>, and
<http://localhost:8000/health/ready>.

### Experiment 1: Predict Configuration Validation

Before running this command, predict whether a database pool of zero will reach
application startup:

```bash
DB_POOL_SIZE=0 uv run python -c "from app.core.config import Settings; Settings()"
```

Expected result: Pydantic rejects the value because `db_pool_size` has `ge=1`.
The lesson is that invalid infrastructure configuration fails at the boundary,
before a request discovers it.

### Experiment 2: Observe Readiness Without Killing Liveness

Start the stack, verify both endpoints, and then stop only PostgreSQL:

```bash
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
docker compose --env-file .env -f infra/local/compose.yaml stop db
curl -i http://localhost:8000/health/live
curl -i http://localhost:8000/health/ready
docker compose --env-file .env -f infra/local/compose.yaml down
```

Prediction: liveness remains `200`, while readiness becomes `503`. This is the
operational distinction encoded by the two handlers.

## Continuous-Learning Loop

Use this loop when Phase 2 adds models, migrations, and seed data:

1. Define the user-visible goal, such as "a fresh database can be seeded."
2. Name the enabling concept, such as an Alembic migration or transaction.
3. Implement the smallest useful path through the existing application factory
   and configuration boundaries.
4. Prove pure decisions with a unit test and PostgreSQL behavior with an
   integration test.
5. Treat failures as boundary information: configuration, application wiring,
   SQL behavior, or container orchestration.
6. Record the transferable lesson in the plan or learning guide before moving
   to the next behavior.

In short:

```text
goal -> principle -> smallest change -> cheapest meaningful proof
     -> failure lesson -> reusable takeaway
```
