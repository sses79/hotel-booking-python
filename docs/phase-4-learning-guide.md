# Phase 4 Learning Guide

Phase 4 turns observed room availability into a durable reservation. The main
challenge is concurrency: two individually valid requests must not reserve the
same room for overlapping dates. The implementation combines clear layer
ownership, one request transaction, PostgreSQL row locks, and a database
constraint that remains correct even when application code is bypassed.

## The 80/20 View

Five ideas explain most of Phase 4:

1. The route owns the transaction; the service coordinates the use case; the
   repository owns selection SQL.
2. A booking request selects one deterministic suitable room and locks it with
   `FOR UPDATE SKIP LOCKED`.
3. The database exclusion constraint is the final protection against
   overlapping stays.
4. Half-open date ranges make checkout-day room reuse valid everywhere.
5. Fast unit tests prove pure contracts, while real-PostgreSQL tests prove
   transactions, constraints, and concurrency.

## 1. One Request Owns One Transaction

[`app/api/routes/bookings.py`](../app/api/routes/bookings.py) opens the
transaction:

```python
async with session.begin():
    booking = await create_booking(session, request)
```

The route owns HTTP details: `201 Created`, the `Location` header, and response
serialization. [`app/services/bookings.py`](../app/services/bookings.py) owns
the booking sequence: confirm the hotel, validate dates, select a room, create
the ORM entity, and flush it. The service neither commits nor creates a session.
[`app/repositories/bookings.py`](../app/repositories/bookings.py) owns the SQL
for room selection and reference lookup.

`flush()` sends the insert to PostgreSQL while the transaction is still open.
This makes constraint failures visible inside the use case. Leaving
`session.begin()` normally commits; an exception causes rollback.

Transferable lesson: put the transaction boundary around the complete business
operation, then let inner layers participate through the same session.

## 2. Lock The Choice, Not The Availability Page

The room query filters by hotel, capacity, optional type, and absence of an
overlapping booking. It orders by capacity, room type, and room number before
choosing one row. The stable order avoids arbitrary allocation and prefers the
smallest suitable capacity.

The important addition is:

```python
.limit(1)
.with_for_update(skip_locked=True)
```

`FOR UPDATE` holds a lock on the selected room until commit or rollback. If a
concurrent transaction already locked that room, `SKIP LOCKED` lets PostgreSQL
move to another suitable room instead of waiting. When no unlocked candidate
remains, the service raises `ConflictError(code="no_room_available", ...)`.

This is stronger than calling the Phase 3 availability endpoint and booking
later. Those would be separate observations with a race between them.

Transferable lesson: when a choice leads to a write, select and lock the chosen
resource inside the write transaction.

## 3. The Database Owns The Non-Overlap Invariant

Application locking is coordination; the database constraint is correctness.
[`migrations/versions/20260806_0002_prevent_booking_overlap.py`](../migrations/versions/20260806_0002_prevent_booking_overlap.py)
enables `btree_gist` and adds this exclusion rule:

```sql
EXCLUDE USING gist (
    room_id WITH =,
    daterange(check_in_date, check_out_date, '[)') WITH &&
)
```

PostgreSQL rejects two rows when both conditions are true: their `room_id`
values are equal and their date ranges overlap. The same invariant appears in
the SQLAlchemy `Booking` model in
[`app/db/models.py`](../app/db/models.py), keeping ORM metadata aligned with the
migration.

If the named constraint rejects `flush()`, the service translates that specific
`IntegrityError` into the same safe `409 no_room_available` response. Other
integrity errors are re-raised instead of being mislabeled. This protection
also applies to scripts, future endpoints, and direct SQL that bypass the
booking service.

Transferable lesson: enforce invariants that must survive every write path in
the database, and translate only failures you can identify precisely.

## 4. One Date Convention Connects Search And Booking

Every stay is represented as `[check_in, check_out)`: check-in is occupied and
check-out is free. Application selection uses:

```text
existing.check_in < requested.check_out
requested.check_in < existing.check_out
```

The exclusion constraint uses PostgreSQL's matching `'[)'` range. Therefore a
booking ending on September 3 and another starting on September 3 do not
overlap. Reusing the Phase 3 `validate_stay_dates()` function also keeps the
same rule that checkout must be later than check-in.

Transferable lesson: represent a domain rule consistently in validation, SQL
queries, constraints, and tests. A mismatch at any boundary creates edge-case
bugs.

## 5. Public References Are Separate From Database IDs

`generate_booking_reference()` uses `secrets.token_hex(16).upper()`, producing
a 128-bit, 32-character uppercase hexadecimal value. The database gives it a
unique constraint, while the lookup route validates the same shape before
querying. A successful create response returns the reference and points its
`Location` header to `/api/v1/bookings/{reference}`.

The UUID remains the internal row identity. The random reference is the public
lookup capability. Phase 4 does not add authentication, so anyone holding a
valid reference can retrieve that booking; authentication remains outside the
MVP.

Transferable lesson: public identifiers can have different security and API
requirements from internal primary keys.

## Execution Flow

```text
POST /api/v1/bookings
  -> FastAPI validates BookingCreate
  -> route begins transaction
  -> service confirms hotel and validates stay dates
  -> repository filters, orders, and locks one suitable Room
       no candidate -> ConflictError
  -> service generates reference, adds Booking, and flushes
       overlap constraint -> named IntegrityError -> ConflictError
  -> transaction commits
  -> route returns 201 + Location + BookingResponse

ConflictError
  -> transaction rolls back
  -> ApplicationError handler in app/main.py
  -> 409 ProblemResponse with code "no_room_available"

GET /api/v1/bookings/{reference}
  -> FastAPI validates 32 uppercase hexadecimal characters
  -> repository selects by unique reference
  -> booking found: 200 BookingResponse
  -> booking absent: NotFoundError -> 404 ProblemResponse
```

## What The Tests Prove

| Boundary | Evidence | Confidence gained | Important limit |
| --- | --- | --- | --- |
| Schema and reference | `test_booking_service.py` | Blank names fail and references have the intended shape | Randomness quality is delegated to `secrets` |
| OpenAPI | `test_booking_routes.py` | Create and lookup routes are published | It does not execute a request |
| Create and lookup | `test_bookings.py` | A booking commits, returns `Location`, and is retrievable | It uses the seeded demo catalog |
| Date and capacity edges | Integration tests | Back-to-back reuse succeeds and unsuitable capacity returns `409` | It does not explore every room combination |
| Concurrent final room | Two requests run with `asyncio.gather()` | Exactly one request wins the last candidate and one conflicts | It is a focused two-request race, not a load test |
| Database invariant | Direct overlapping ORM inserts | PostgreSQL rejects overlap using the expected constraint | PostgreSQL is required; SQLite cannot prove it |

## Try It

Start PostgreSQL, apply migrations, and run the API:

```bash
test -f .env || cp .env.example .env
docker compose --env-file .env -f infra/local/compose.yaml up -d db
uv sync --frozen --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
curl -X POST http://localhost:8000/api/v1/admin/seed
```

Create a booking with future dates, then follow its returned `Location`:

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

Run the focused tests:

```bash
uv run pytest tests/unit/test_booking_service.py tests/unit/test_booking_routes.py
TEST_DATABASE_URL=postgresql+asyncpg://hotel_booking:hotel_booking_local@localhost:5432/hotel_booking \
  uv run pytest tests/integration/test_bookings.py
```

### Experiment 1: Predict The Boundary

Create a second booking for the same room type with check-in equal to the first
booking's checkout. Predict `201`, then change its check-in to one day earlier.
The first request should allow checkout-day reuse; the overlapping request may
use another suitable room and returns `409` only when all matching rooms are
occupied. This separates a room-level invariant from hotel-level availability.

### Experiment 2: Observe Transaction Ownership

Run the concurrent integration test with `-v`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://hotel_booking:hotel_booking_local@localhost:5432/hotel_booking \
  uv run pytest tests/integration/test_bookings.py::test_concurrent_requests_only_book_the_final_suitable_room -v
```

Before temporarily removing `skip_locked=True`, predict the behavioral change:
the second request can wait for the locked row rather than immediately consider
another candidate. Restore the code after the experiment. The exclusion
constraint should remain untouched because it is the final safety rule.

## Continuous-Learning Loop

Use this loop for the next transactional feature:

1. Define the user-visible goal, such as “cancel one existing booking.”
2. Name the core concept that enables it: transaction, lock, constraint, or
   idempotency rule.
3. Implement the smallest useful behavior within one clear transaction owner.
4. Prove pure validation cheaply, then test persistence behavior against real
   PostgreSQL.
5. Classify failures by boundary: HTTP validation, domain decision, selection
   query, transaction race, or database invariant.
6. Record why the proof is sufficient and what it does not cover.

```text
goal -> principle -> smallest change -> cheapest meaningful proof
     -> failure lesson -> reusable takeaway
```
