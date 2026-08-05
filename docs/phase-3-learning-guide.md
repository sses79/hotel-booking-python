# Phase 3 Learning Guide

Phase 3 makes the Phase 2 data model useful through public read APIs. A client
can find the seeded hotel and ask which rooms satisfy a stay, guest count, and
optional room type. The deeper value is the query boundary: HTTP validation,
domain rules, SQL filtering, response serialization, and known failures each
have one clear owner.

## The 80/20 View

Five ideas explain most of Phase 3:

1. Routes translate HTTP, services express use-case rules, and repositories own
   SQLAlchemy queries.
2. Half-open date ranges reduce availability to two strict overlap comparisons.
3. A correlated `NOT EXISTS` query asks PostgreSQL for only suitable, free
   rooms instead of filtering rows in Python.
4. FastAPI validation errors and known application errors belong to different
   response boundaries.
5. Availability is an observation, not a reservation; Phase 4 must add locking
   and a database overlap guard.

Together, these ideas explain the complete request path and show exactly where
the next phase must strengthen it.

## 1. Each Layer Owns One Kind Of Decision

[`app/api/routes/hotels.py`](../app/api/routes/hotels.py) owns HTTP concerns:

- paths and methods;
- query parameter types and simple bounds;
- documented response models and status codes; and
- conversion from returned ORM objects to public Pydantic schemas.

The route does not construct SQL or decide whether dates form a valid stay. It
passes the request-scoped `AsyncSession` and typed values to
[`app/services/hotels.py`](../app/services/hotels.py).

The service owns use-case meaning. It trims a hotel name, rejects a blank name,
validates stay dates, distinguishes an unknown hotel from an empty result, and
coordinates repository calls. It does not know about `Query`, JSON, or
`JSONResponse`.

[`app/repositories/hotels.py`](../app/repositories/hotels.py) owns persistence
questions. It contains the exact-name hotel query, primary-key lookup, and room
availability statement. It returns ORM entities but does not turn missing rows
into HTTP errors.

```text
HTTP shape             use-case meaning          persistence
route                  service                   repository
Query/UUID/date  ->    date rules/not found ->  SELECT/EXISTS/ORDER BY
```

This is deliberately not a generic repository framework. Each function answers
one concrete question required by the application.

Transferable lesson: split code at decision boundaries, not merely to create
more files. A layer earns its place when it isolates a kind of change.

## 2. Half-Open Dates Make Boundaries Predictable

A stay uses the half-open interval:

```text
[check_in, check_out)
```

The check-in date is occupied; the check-out date is not. This permits one
guest to check in on the day another checks out.

Two stays overlap exactly when both strict comparisons are true:

```text
existing.check_in < requested.check_out
requested.check_in < existing.check_out
```

The repository encodes those comparisons against `Booking`:

```python
Booking.check_in_date < check_out_date
check_in_date < Booking.check_out_date
```

Strict `<` is the important detail. Replacing either comparison with `<=`
would incorrectly treat back-to-back stays as overlapping.

Before querying availability, `validate_stay_dates()` enforces two different
rules:

- check-in must be today or later; and
- check-out must be after check-in.

Its optional `today` argument is an intentional testing seam. Production uses
`date.today()`, while unit tests supply a fixed date and remain deterministic.

Transferable lesson: choose an interval convention once, write down its overlap
equation, and test the touching-boundary case. Most date bugs hide at equality.

## 3. PostgreSQL Filters Rows Before Python Sees Them

The availability repository builds one SQL statement with four responsibilities:

```text
same hotel
AND capacity >= guests
AND optional room_type matches
AND NOT EXISTS an overlapping booking for this room
```

The `EXISTS` subquery is correlated through:

```python
Booking.room_id == Room.id
```

For each candidate room, PostgreSQL only needs to determine whether one
overlapping booking exists. Negating that predicate selects rooms for which no
such booking exists. The application receives only the result rows; it does not
load every room and booking to reproduce relational logic in memory.

Results are ordered by capacity, room type, and room number. This makes API
responses deterministic and places smaller suitable rooms first. Stable order
also gives Phase 4 a natural candidate order for transactional room selection.

The hotel lookup uses an exact name because Phase 2 enforces an exact unique
hotel-name constraint. Whitespace around the query is stripped by the service,
but case and internal characters retain their database meaning. A future
case-insensitive lookup should be paired with a matching case-insensitive
uniqueness strategy rather than quietly changing only the query.

Transferable lesson: let the database perform set selection, and make ordering
explicit whenever callers or later write paths depend on predictable results.

## 4. Validation And Errors Cross Different Boundaries

FastAPI validates values it can understand from one parameter:

- `hotel_id` must be a UUID;
- dates must use an accepted date format;
- `guests` must be at least one; and
- `room_type` must be a `RoomType` value.

Failures at this boundary produce FastAPI's standard `422` response because the
request could not become valid typed inputs.

Cross-field and resource rules belong to the service. For example, each date is
individually valid in `check_in=2027-09-03&check_out=2027-09-01`, but together
they do not form a stay. The service raises `BadRequestError` with a stable code
such as `invalid_date_range`. Missing hotels raise `NotFoundError` with
`hotel_not_found`.

[`app/core/errors.py`](../app/core/errors.py) defines these known application
errors without importing route code. [`app/main.py`](../app/main.py) registers
one handler that converts any `ApplicationError` into the public
[`ProblemResponse`](../app/schemas/errors.py):

```json
{
  "code": "hotel_not_found",
  "message": "Hotel not found",
  "details": {"name": "Unknown Hotel"}
}
```

The route advertises the `400` and `404` models in OpenAPI. Unexpected bugs are
not caught by this handler and therefore are not disguised as known client
errors.

Transferable lesson: distinguish failure to parse input from rejection of valid
typed input. Give expected domain failures stable codes while allowing unknown
failures to remain visible operationally.

## 5. Public Schemas Prevent ORM Leakage

[`app/schemas/hotels.py`](../app/schemas/hotels.py) defines the fields that leave
the API. `ConfigDict(from_attributes=True)` lets Pydantic read those fields from
ORM objects, but the routes still call `model_validate()` explicitly instead of
returning ORM instances directly.

This boundary matters because an ORM model contains persistence concerns such
as relationships and lazy-loading behavior. A response schema is a versioned
public contract. Adding an internal relationship does not accidentally add it
to JSON, and `lazy="raise"` relationships are never traversed during response
serialization.

`AvailableRoomResponse` contains identity, hotel identity, room number, type,
and capacity. It does not expose bookings or invent an `available` flag: every
returned row is available for the specific query, while an empty list is a
successful search with no matches.

Transferable lesson: serialize through explicit API models. Persistence shape
and public shape often begin similarly, but they evolve for different reasons.

## Critical Boundary: Availability Is Not A Booking Guarantee

The Phase 3 endpoint performs a read:

```text
query says room 201 is free
  -> another request may book room 201
  -> the original client has not reserved anything
```

No row lock is held after the response, and Phase 3 adds no exclusion constraint
for overlapping bookings. That is correct for search, but unsafe for booking
creation if reused as “check, then insert.”

Phase 4 must perform candidate selection and insertion in one transaction,
using row locking and a PostgreSQL exclusion constraint as the final guard. It
can reuse the half-open equation and stable ordering, but it cannot treat the
Phase 3 response as a promise.

Transferable lesson: read models describe observed state. Correct writes need
their own atomicity and concurrency design.

## Execution Flow

### Hotel Lookup

```text
GET /api/v1/hotels?name=Grand Plaza Hotel
  -> FastAPI validates name length and creates AsyncSession
  -> route calls get_hotel_by_name()
  -> service trims whitespace
  -> repository SELECTs exact unique name
     -> found: HotelResponse.model_validate() -> 200 JSON
     -> absent: NotFoundError -> global handler -> 404 ProblemResponse
  -> request dependency closes AsyncSession
```

### Room Availability

```text
GET /api/v1/hotels/{id}/rooms/available
  ?check_in=2027-09-01&check_out=2027-09-03&guests=2
  -> FastAPI parses UUID, dates, integer, and optional enum
  -> repository confirms hotel exists
  -> service validates dates
  -> repository SELECTs rooms
       hotel matches
       capacity fits
       optional type matches
       NOT EXISTS overlapping Booking
       ORDER BY capacity, type, room number
  -> route maps ORM rows to AvailableRoomResponse list
  -> 200 JSON, including [] when no room matches
```

Phase 3 is read-only, so it requires no new migration and no explicit commit.
The request session still scopes database resources and closes after the
response.

## What The Tests Prove

| Boundary | Evidence | Confidence gained | Important limit |
| --- | --- | --- | --- |
| OpenAPI contract | `test_hotel_routes.py` inspects generated paths | Both public routes remain documented | It does not call PostgreSQL |
| Date rules | `test_hotel_service.py` injects a fixed `today` | Today, past dates, and invalid ranges are deterministic | It does not prove SQL overlap behavior |
| Lookup and error mapping | Integration lookup test calls the ASGI app | Seeded hotel and `404` problem shape work end to end | Lookup is exact, not fuzzy |
| Capacity, type, and ordering | Integration availability test checks returned room numbers | PostgreSQL filters and stable order match the API contract | Only the seeded catalog is exercised |
| Half-open overlap | Integration test inserts a booking directly | Overlap excludes a room and checkout-day reuse includes it | It is not a concurrent booking test |
| Input validation | Integration test sends `guests=0` | FastAPI returns `422` before repository work | Not every malformed parameter is enumerated |

The full suite also retains Phase 1 health checks and Phase 2 migration,
constraint, seed, and reset coverage. Phase 3 tests do not prove booking
creation, overlap prevention under concurrency, or booking reference lookup.

## Try It

Start PostgreSQL, migrate, seed, and run the API:

```bash
test -f .env || cp .env.example .env
docker compose --env-file .env -f infra/local/compose.yaml up -d db
uv sync --frozen --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
curl -X POST http://localhost:8000/api/v1/admin/seed
```

Find the seeded hotel and suitable rooms:

```bash
curl --get http://localhost:8000/api/v1/hotels \
  --data-urlencode "name=Grand Plaza Hotel"

curl --get \
  http://localhost:8000/api/v1/hotels/00000000-0000-0000-0000-000000000001/rooms/available \
  --data-urlencode "check_in=2027-09-01" \
  --data-urlencode "check_out=2027-09-03" \
  --data-urlencode "guests=2"
```

Run the focused Phase 3 tests:

```bash
uv run pytest tests/unit/test_hotel_service.py tests/unit/test_hotel_routes.py
TEST_DATABASE_URL=postgresql+asyncpg://hotel_booking:hotel_booking_local@localhost:5432/hotel_booking \
  uv run pytest tests/integration/test_hotels.py
```

### Experiment 1: Predict Capacity Filtering

With the seeded catalog, predict the room numbers returned for `guests=3`
before sending the request. Then change only the `guests` value above.

Expected result: rooms `301` and `302`, because each has capacity four. The
single and double rooms are eliminated in PostgreSQL by `capacity >= guests`.

### Experiment 2: Observe Validation Ownership

Compare these two requests:

```bash
curl -i --get \
  http://localhost:8000/api/v1/hotels/00000000-0000-0000-0000-000000000001/rooms/available \
  --data-urlencode "check_in=not-a-date" \
  --data-urlencode "check_out=2027-09-03" \
  --data-urlencode "guests=2"

curl -i --get \
  http://localhost:8000/api/v1/hotels/00000000-0000-0000-0000-000000000001/rooms/available \
  --data-urlencode "check_in=2027-09-03" \
  --data-urlencode "check_out=2027-09-01" \
  --data-urlencode "guests=2"
```

Prediction: the malformed date produces FastAPI's `422`; the valid dates in an
invalid order produce the application's `400` problem response. Trace each one
to the layer that owns the decision.

### Experiment 3: Protect The Checkout Boundary

Run the focused integration test:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://hotel_booking:hotel_booking_local@localhost:5432/hotel_booking \
  uv run pytest tests/integration/test_hotels.py::test_availability_uses_half_open_dates_and_maps_known_errors -v
```

Before changing either `<` comparison in the repository to `<=`, predict which
assertion would fail. Do not keep that experimental change: equality is exactly
what permits checkout-day reuse.

## Continuous-Learning Loop

Use this loop when Phase 4 turns observed availability into a booking:

1. Define the user-visible goal, such as “reserve one suitable room exactly
   once.”
2. Name the enabling concept: atomic selection and insertion under PostgreSQL
   concurrency control.
3. Implement the smallest transaction that locks candidates, checks overlap,
   inserts a booking, and commits.
4. Prove pure rules cheaply, then use concurrent PostgreSQL tests for the final
   room race.
5. Classify failures by boundary: request validation, service rule, query,
   transaction lock, or database constraint.
6. Record the reusable lesson, especially why an availability read could not
   guarantee a later write.

In short:

```text
goal -> principle -> smallest change -> cheapest meaningful proof
     -> failure lesson -> reusable takeaway
```
