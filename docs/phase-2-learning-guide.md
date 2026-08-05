# Phase 2 Learning Guide

Phase 2 turns the Phase 1 application shell into a database-backed system. A
fresh PostgreSQL database can now be migrated to a known schema, populated with
stable demo data, and reset through the API. The important result is not merely
three tables: it is a clear division between ORM intent, migration history,
request transactions, and database-enforced correctness.

## The 80/20 View

Five ideas explain most of Phase 2:

1. Put invariants in PostgreSQL when invalid data must be impossible, regardless
   of which code path writes it.
2. Give every request its own SQLAlchemy session, but let the route own the
   transaction boundary.
3. Treat Alembic migrations as database history and ORM metadata as the current
   application model.
4. Make destructive demo operations deterministic, environment-limited, and
   safe under concurrent calls.
5. Test PostgreSQL behavior with PostgreSQL; mocks cannot prove constraints,
   migrations, or locking.

These principles create the persistence boundary that search and booking
features can use in later phases.

## 1. The Database Protects Domain Invariants

[`app/db/models.py`](../app/db/models.py) declares `Hotel`, `Room`, and
`Booking` with SQLAlchemy's typed declarative mapping. Python types make the
model convenient to use, but the table constraints provide the strongest
guarantees:

- hotel names and booking references are unique;
- room numbers are unique within a hotel;
- room capacity and booking guest count must be positive;
- check-in must be before check-out;
- room type must be one of the `RoomType` values; and
- a booking's `room_id` and `hotel_id` must identify the same hotel.

The final rule is enforced by a composite foreign key:

```text
bookings(room_id, hotel_id)
  -> rooms(id, hotel_id)
```

PostgreSQL requires the referenced pair to be unique, so `Room` also declares
`uq_rooms_id_hotel_id`. The standalone room ID is already globally unique, but
the pair exists to give the composite foreign key a valid database target. This
prevents a caller from combining a room from Hotel A with Hotel B's ID.

Because hotel identity is derived through the room for the current one-room
booking model, `Booking.hotel` and `Hotel.bookings` are view-only ORM
relationships. The room relationship is the write path. `lazy="raise"` on the
relationships also prevents an accidental database query when unloaded related
data is accessed; queries must choose eager loading explicitly.

`ROOM_TYPE_CHECK_SQL` is generated from `RoomType`, so the Python enum and the
ORM check expression cannot acquire different value lists. A new room type
still requires a migration because the deployed database constraint is a
versioned schema object.

[`app/db/base.py`](../app/db/base.py) provides deterministic names for primary
keys, foreign keys, indexes, unique constraints, and checks. For a check such
as `name="positive_capacity"`, the naming convention produces the final name
`ck_rooms_positive_capacity`. Stable names make migration reviews and database
errors easier to understand.

Transferable lesson: application validation improves error messages, but
database constraints protect every writer, including future routes, scripts,
and manual SQL.

### Boundary: Multiple Rooms Per Booking

The current schema intentionally represents one room per booking. Supporting
multiple rooms would introduce a `booking_rooms` association table rather than
adding arrays or numbered room columns:

```text
Booking 1 -> many BookingRoom rows -> many Rooms
```

The association can carry room-specific occupancy, price, or status. Composite
foreign keys through `hotel_id` can preserve the same rule that every selected
room belongs to the booking's hotel. This would be a new migration and domain
change; the Phase 2 constraint does not prevent that evolution.

## 2. Sessions And Transactions Have Different Owners

[`app/db/session.py`](../app/db/session.py) builds one process-wide async engine
and one session factory. The engine owns the connection pool; it is not a
connection itself. `pool_pre_ping=True` checks a pooled connection before reuse,
and the pool size comes from validated settings.

The application factory in [`app/main.py`](../app/main.py) stores the engine and
session factory on `application.state`. Its lifespan disposes the engine during
shutdown.

[`app/api/dependencies.py`](../app/api/dependencies.py) creates one
`AsyncSession` per request:

```text
request
  -> FastAPI resolves SessionDep
  -> session factory opens AsyncSession
  -> route and service share that session
  -> dependency closes the session after the response
```

The dependency owns session lifetime, but it does not commit. The admin route
owns the use-case transaction with `async with session.begin()`. This is an
important separation:

```text
route = begin, commit, or roll back the complete use case
service = perform database work inside the supplied transaction
```

[`app/services/seed.py`](../app/services/seed.py) calls `flush()` after adding
the object graph. Flush sends pending SQL to PostgreSQL so constraint failures
happen before the service returns, but it does not commit. The surrounding
route transaction commits on success and rolls back on an exception.

`expire_on_commit=False` allows the route to read the seeded IDs and name after
commit without triggering an implicit async refresh.

Transferable lesson: scope a session to one request and a transaction to one
business operation. Avoid hidden commits in reusable services because callers
then lose atomic control.

## 3. Models Describe Today; Migrations Preserve History

The application never calls `Base.metadata.create_all()`. Schema creation is an
explicit deployment step owned by Alembic.

[`migrations/env.py`](../migrations/env.py) connects Alembic to the application:

- importing `app.db.models` registers every mapped table;
- `Base.metadata` becomes `target_metadata` for autogeneration and drift checks;
- `DATABASE_URL` overrides the local Alembic default;
- the async engine uses `NullPool` because a migration process does not need a
  long-lived application pool; and
- `connection.run_sync()` bridges the async driver to Alembic's synchronous
  migration context.

[`migrations/versions/20260804_0001_initial_schema.py`](../migrations/versions/20260804_0001_initial_schema.py)
is the immutable initial schema snapshot. Its `upgrade()` creates tables in
dependency order, then indexes and constraints. Its `downgrade()` removes them
in reverse dependency order.

The migration contains the literal room-type values that existed when it was
created. It should not import the current `RoomType` enum: changing application
code later must not rewrite what an old migration means. Instead, adding a room
type requires a new migration that changes the deployed check constraint.

There are three distinct commands:

```text
alembic upgrade head        apply committed history
alembic downgrade -1        reverse the latest revision
alembic check               compare current metadata with migrated schema
```

[`infra/local/compose.yaml`](../infra/local/compose.yaml) packages migration as
an explicit `migrate` service. The production-shaped
[`Dockerfile`](../Dockerfile) includes `alembic.ini` and `migrations/`, allowing
the same image to run either the API or a one-off migration command.

Transferable lesson: do not let application startup silently mutate schemas.
Deploy schema history deliberately before starting code that depends on it.

## 4. Demo Data Is Deterministic And Serialized

[`app/services/seed.py`](../app/services/seed.py) uses fixed UUIDs and a fixed
room catalog. Calling seed repeatedly therefore produces the same observable
dataset:

```text
1 hotel + 6 rooms + 0 bookings
```

Seed is a rebuild, not an append:

```text
acquire transaction advisory lock
  -> delete bookings
  -> delete rooms
  -> delete hotels
  -> insert deterministic hotel and rooms
  -> flush
  -> route commits
```

Deletion follows foreign-key dependency order. Although cascading rules also
exist, the explicit sequence makes the reset operation's intent visible.

Both seed and reset call PostgreSQL's `pg_advisory_xact_lock()` with the same
application lock ID. If two requests arrive together, one transaction waits
for the other instead of racing to delete and insert the same primary keys. The
lock is released automatically when the route's transaction ends, including on
rollback.

[`app/api/routes/admin.py`](../app/api/routes/admin.py) exposes this behavior as
`POST /api/v1/admin/seed` and `POST /api/v1/admin/reset`. In
[`app/main.py`](../app/main.py), the router is registered only for `local` and
`test`. It is absent from both routing and OpenAPI in `dev` and `prod`.

These endpoints are intentionally unauthenticated for the demo because
authentication is outside the MVP. As documented in [`README.md`](../README.md),
an application running in local or test mode must not be exposed to an
untrusted network. Environment gating is an operational boundary, not user
authorization.

Transferable lesson: idempotent-looking setup operations still need concurrency
design. Stable IDs make results repeatable; a shared transactional lock makes
simultaneous execution repeatable too.

## 5. Confidence Comes From Crossing The Real Boundary

[`tests/integration/conftest.py`](../tests/integration/conftest.py) applies the
Alembic migration once per test session when `TEST_DATABASE_URL` is present.
Without that variable, database integration tests skip rather than silently
using a developer database.

[`tests/integration/test_seed.py`](../tests/integration/test_seed.py) uses the
real application, asyncpg, SQLAlchemy, and PostgreSQL. It proves that:

- sequential seed calls return the same response and leave one stable dataset;
- two concurrent seed requests both succeed;
- reset removes all hotels, rooms, and bookings;
- PostgreSQL rejects non-positive room capacity;
- PostgreSQL rejects non-positive guest counts and invalid date ranges; and
- PostgreSQL rejects a booking whose hotel does not own its room.

These are integration tests because the behavior depends on PostgreSQL
transactions and constraints. Replacing the database with a mock would only
prove that certain methods were called.

[`tests/unit/test_admin_routes.py`](../tests/unit/test_admin_routes.py) tests a
cheaper boundary: route registration. It builds applications with different
settings and confirms destructive routes exist locally but not in `dev` or
`prod`.

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) starts PostgreSQL 16,
installs the frozen dependency graph, runs static checks, applies migrations,
and then runs the complete suite. CI therefore cannot accidentally pass by
skipping the database tests.

Transferable lesson: use the cheapest boundary that can prove the risk. Route
visibility is a unit test; database enforcement and transaction locking require
real PostgreSQL.

## Execution Flow

### Seed Request

```text
POST /api/v1/admin/seed
  -> FastAPI resolves request-scoped AsyncSession
  -> route begins transaction
  -> seed service acquires PostgreSQL advisory lock
  -> existing Booking, Room, and Hotel rows are deleted
  -> deterministic Hotel with six Rooms is added
  -> flush checks SQL and database constraints
  -> route transaction commits and releases lock
  -> SeedResponse is serialized as JSON
  -> dependency closes session
```

If any SQL statement fails, `session.begin()` rolls back the entire rebuild. A
caller does not observe a half-deleted or half-seeded dataset.

### Fresh Database

```text
DATABASE_URL
  -> Alembic async environment
  -> initial migration upgrade()
  -> hotels
  -> rooms and their hotel foreign key
  -> bookings and their hotel/room constraints
  -> indexes
  -> schema revision recorded in alembic_version
```

### Continuous Integration

```text
push or pull request
  -> disposable PostgreSQL 16 service becomes healthy
  -> uv installs uv.lock exactly
  -> Ruff + format + mypy
  -> alembic upgrade head
  -> unit and PostgreSQL integration tests
  -> required quality result
```

## What The Tests Prove

| Boundary | Evidence | Confidence gained | Important limit |
| --- | --- | --- | --- |
| ORM and PostgreSQL constraints | Invalid rows raise `IntegrityError` | Critical invariants survive any writer | Not every unique or cascade rule has a focused test |
| Hotel/room consistency | Cross-hotel booking insert fails | Denormalized IDs cannot disagree | Current model supports one room per booking |
| Seed transaction | Repeat and concurrent request tests | Rebuild is stable and serialized | It intentionally deletes all demo data |
| Route exposure | OpenAPI path assertions by environment | Admin routes are absent in `dev` and `prod` | Local/test routes have no authentication by design |
| Migration startup | Session fixture and CI run `upgrade head` | Tests use the committed schema | CI does not currently test downgrade |
| Static checks | Ruff and strict mypy | Typed interfaces and common defects are checked | Static analysis cannot prove SQL behavior |

Phase 2 does not yet prove hotel search, availability, overlap prevention,
booking creation, or booking lookup. Those are Phase 3 and Phase 4 behaviors.

## Try It

Create local configuration, start PostgreSQL, and apply the schema:

```bash
test -f .env || cp .env.example .env
docker compose --env-file .env -f infra/local/compose.yaml up -d db
uv sync --frozen --all-groups
uv run alembic upgrade head
uv run alembic check
```

Run every check with the real database:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
TEST_DATABASE_URL=postgresql+asyncpg://hotel_booking:hotel_booking_local@localhost:5432/hotel_booking \
  uv run pytest
```

Run the API and exercise the deterministic operations:

```bash
uv run uvicorn app.main:app --reload
curl -X POST http://localhost:8000/api/v1/admin/seed
curl -X POST http://localhost:8000/api/v1/admin/seed
curl -i -X POST http://localhost:8000/api/v1/admin/reset
```

The two seed responses should match. Reset should return `204 No Content`.

### Experiment 1: Inspect Constraint Naming

Before running this command, predict the final name of the ORM constraint whose
local token is `positive_capacity`:

```bash
uv run python -c "from app.db.models import Room; print(sorted(c.name for c in Room.__table__.constraints))"
```

Expected result: the output includes `ck_rooms_positive_capacity`. SQLAlchemy's
naming convention expands the local token into the same stable name recorded in
the migration.

### Experiment 2: Prove The Concurrency Boundary

Run only the concurrent seed test against local PostgreSQL:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://hotel_booking:hotel_booking_local@localhost:5432/hotel_booking \
  uv run pytest tests/integration/test_seed.py::test_concurrent_seed_requests_are_serialized -v
```

Prediction: both simultaneous requests return `200`, and the final counts are
one hotel, six rooms, and zero bookings. Then inspect
`_acquire_demo_data_lock()` and identify where the lock is released: not in the
service, but when the route transaction commits or rolls back.

### Experiment 3: Observe Environment Gating

This experiment needs no running database:

```bash
APP_ENV=prod uv run python -c "from app.main import app; print('/api/v1/admin/seed' in app.openapi()['paths'])"
```

Expected result: `False`. Change `APP_ENV` to `local` and predict the result
before rerunning it.

## Continuous-Learning Loop

Use this loop when Phase 3 adds search and availability:

1. Define the user-visible goal, such as "return rooms that fit two guests."
2. Name the enabling concept, such as a capacity filter or half-open date-range
   overlap query.
3. Implement the smallest useful path through the existing session and
   transaction boundaries.
4. Prove pure request or response decisions cheaply, then cross into PostgreSQL
   for query semantics that depend on real SQL.
5. Classify failures by boundary: validation, route wiring, transaction scope,
   ORM query, migration, or database constraint.
6. Record the lesson that should shape the next change, especially where the
   database must guarantee correctness independently of application code.

In short:

```text
goal -> principle -> smallest change -> cheapest meaningful proof
     -> failure lesson -> reusable takeaway
```
