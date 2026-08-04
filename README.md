# Hotel Booking API

A demo hotel room booking API built with Python 3.14, FastAPI, SQLAlchemy, and
PostgreSQL. Local development uses Docker Compose; AWS deployment will use
Terraform.

The MVP focuses on hotel search, room availability, booking creation, booking
lookup, and deterministic seed/reset behavior. Authentication, frontend, and
payments are intentionally outside the MVP. See the full
[implementation plan](docs/plan.md).

## Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Docker with Docker Compose

## Run Locally

Create local configuration and start the API with PostgreSQL:

```bash
cp .env.example .env
docker compose --env-file .env -f infra/local/compose.yaml up --build
```

Open:

- API documentation: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/health/live>
- Readiness: <http://localhost:8000/health/ready>

Stop the containers without deleting database data:

```bash
docker compose --env-file .env -f infra/local/compose.yaml down
```

To intentionally remove the local PostgreSQL volume as well:

```bash
docker compose --env-file .env -f infra/local/compose.yaml down --volumes
```

## Develop Without The API Container

Start only PostgreSQL, install dependencies, and run the API:

```bash
cp .env.example .env
docker compose --env-file .env -f infra/local/compose.yaml up -d db
uv sync --frozen
uv run uvicorn app.main:app --reload
```

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

The PostgreSQL readiness integration test runs when `TEST_DATABASE_URL` is set:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://hotel_booking:hotel_booking_local@localhost:5432/hotel_booking \
  uv run pytest
```

## Configuration

Settings are read from environment variables. Safe development defaults are
documented in `.env.example`; `.env` and secrets must not be committed.

## License

This project is available under the [MIT License](LICENSE).
