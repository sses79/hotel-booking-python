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
test -f .env || cp .env.example .env
docker compose --env-file .env -f infra/local/compose.yaml up -d db
docker compose --env-file .env -f infra/local/compose.yaml run --rm --build migrate
docker compose --env-file .env -f infra/local/compose.yaml up --build api
```

Open:

- API documentation: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/health/live>
- Readiness: <http://localhost:8000/health/ready>

Create or reset the deterministic local dataset:

```bash
curl -X POST http://localhost:8000/api/v1/admin/seed
curl -X POST http://localhost:8000/api/v1/admin/reset
```

These destructive demo routes are intentionally unauthenticated because
authentication is outside the MVP. They are registered only when `APP_ENV` is
`local` or `test`; never expose an instance using either environment value to
an untrusted network.

Find the seeded hotel by its exact name:

```bash
curl --get http://localhost:8000/api/v1/hotels \
  --data-urlencode "name=Grand Plaza Hotel"
```

Find suitable rooms that are free for the full half-open stay
`[check_in, check_out)`:

```bash
curl --get \
  http://localhost:8000/api/v1/hotels/00000000-0000-0000-0000-000000000001/rooms/available \
  --data-urlencode "check_in=2027-09-01" \
  --data-urlencode "check_out=2027-09-03" \
  --data-urlencode "guests=2" \
  --data-urlencode "room_type=double"
```

Omit `room_type` to search all room categories. Results are ordered by capacity,
room type, and room number; an empty list means no suitable room is available.

Create a booking for the smallest suitable available room:

```bash
curl -i -X POST http://localhost:8000/api/v1/bookings \
  -H "Content-Type: application/json" \
  -d '{
    "hotel_id": "00000000-0000-0000-0000-000000000001",
    "guest_name": "Ada Lovelace",
    "guest_count": 2,
    "check_in_date": "2027-09-01",
    "check_out_date": "2027-09-03",
    "room_type": "double"
  }'
```

The API returns `201 Created`, a 32-character public booking reference, and a
`Location` header. Use that path to retrieve the booking:

```bash
curl http://localhost:8000/api/v1/bookings/REPLACE_WITH_BOOKING_REFERENCE
```

Booking creation locks candidate rooms inside its transaction. PostgreSQL also
rejects overlapping date ranges for the same room, protecting correctness when
requests race or another write path bypasses the service.

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
test -f .env || cp .env.example .env
docker compose --env-file .env -f infra/local/compose.yaml up -d db
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Database Migrations

Apply all migrations:

```bash
uv run alembic upgrade head
```

Create and review a migration after changing ORM metadata:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

Rollback one revision locally when testing reversibility:

```bash
uv run alembic downgrade -1
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
