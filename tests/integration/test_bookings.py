"""PostgreSQL-backed booking API and concurrency tests."""

import asyncio
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.db.models import BOOKING_OVERLAP_CONSTRAINT, Booking, Room
from app.main import create_app
from app.services.seed import DEMO_HOTEL_ID
from tests.integration.conftest import integration_database_url, session_factory_for

pytestmark = pytest.mark.integration


def booking_payload(
    *,
    check_in: date,
    check_out: date,
    guests: int = 2,
    room_type: str | None = None,
    hotel_id: str | None = None,
) -> dict[str, Any]:
    """Build a valid booking request body with optional selection changes."""

    payload: dict[str, Any] = {
        "hotel_id": hotel_id or str(DEMO_HOTEL_ID),
        "guest_name": "Ada Lovelace",
        "guest_count": guests,
        "check_in_date": check_in.isoformat(),
        "check_out_date": check_out.isoformat(),
    }
    if room_type is not None:
        payload["room_type"] = room_type
    return payload


@pytest.mark.asyncio
async def test_create_lookup_and_overlapping_availability() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    factory = session_factory_for(app)
    transport = httpx.ASGITransport(app=app)
    check_in = date.today() + timedelta(days=2)
    check_out = check_in + timedelta(days=2)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            seeded = await client.post("/api/v1/admin/seed")
            created = await client.post(
                "/api/v1/bookings",
                json=booking_payload(check_in=check_in, check_out=check_out),
            )

            assert seeded.status_code == 200
            assert created.status_code == 201
            created_body = created.json()
            location = created.headers["Location"]
            assert location == f"/api/v1/bookings/{created_body['reference']}"
            assert len(created_body["reference"]) == 32
            assert created_body["guest_name"] == "Ada Lovelace"

            found = await client.get(location)
            assert found.status_code == 200
            assert found.json() == created_body

            async with factory() as session:
                room_number = await session.scalar(
                    select(Room.room_number).where(Room.id == created_body["room_id"])
                )
            assert room_number == "201"

            available = await client.get(
                f"/api/v1/hotels/{DEMO_HOTEL_ID}/rooms/available",
                params={
                    "check_in": check_in.isoformat(),
                    "check_out": check_out.isoformat(),
                    "guests": 2,
                },
            )
            assert available.status_code == 200
            assert created_body["room_id"] not in {
                room["id"] for room in available.json()
            }
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_back_to_back_reuses_room_and_capacity_conflict_is_409() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    transport = httpx.ASGITransport(app=app)
    first_check_in = date.today() + timedelta(days=3)
    first_check_out = first_check_in + timedelta(days=2)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/seed")
            first = await client.post(
                "/api/v1/bookings",
                json=booking_payload(
                    check_in=first_check_in,
                    check_out=first_check_out,
                    room_type="double",
                ),
            )
            second = await client.post(
                "/api/v1/bookings",
                json=booking_payload(
                    check_in=first_check_out,
                    check_out=first_check_out + timedelta(days=1),
                    room_type="double",
                ),
            )
            too_many_guests = await client.post(
                "/api/v1/bookings",
                json=booking_payload(
                    check_in=first_check_in,
                    check_out=first_check_out,
                    guests=3,
                    room_type="double",
                ),
            )

            assert first.status_code == 201
            assert second.status_code == 201
            assert first.json()["room_id"] == second.json()["room_id"]
            assert too_many_guests.status_code == 409
            assert too_many_guests.json()["code"] == "no_room_available"
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_requests_only_book_the_final_suitable_room() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    factory = session_factory_for(app)
    transport = httpx.ASGITransport(app=app)
    check_in = date.today() + timedelta(days=4)
    check_out = check_in + timedelta(days=2)
    payload = booking_payload(
        check_in=check_in,
        check_out=check_out,
        guests=4,
        room_type="deluxe",
    )

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/seed")
            blocker = await client.post("/api/v1/bookings", json=payload)
            assert blocker.status_code == 201

            responses = await asyncio.gather(
                client.post("/api/v1/bookings", json=payload),
                client.post("/api/v1/bookings", json=payload),
            )

            assert sorted(response.status_code for response in responses) == [201, 409]
            conflict = next(
                response for response in responses if response.status_code == 409
            )
            assert conflict.json()["code"] == "no_room_available"

        async with factory() as session:
            booking_count = await session.scalar(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.check_in_date == check_in,
                    Booking.check_out_date == check_out,
                )
            )
        assert booking_count == 2
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_database_exclusion_constraint_rejects_direct_overlap() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    factory = session_factory_for(app)
    transport = httpx.ASGITransport(app=app)
    check_in = date.today() + timedelta(days=5)
    check_out = check_in + timedelta(days=2)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/seed")

        async with factory.begin() as session:
            room_id = await session.scalar(
                select(Room.id).where(Room.room_number == "101")
            )
            assert room_id is not None
            session.add(
                Booking(
                    reference=uuid4().hex.upper(),
                    hotel_id=DEMO_HOTEL_ID,
                    room_id=room_id,
                    guest_name="First Guest",
                    guest_count=1,
                    check_in_date=check_in,
                    check_out_date=check_out,
                )
            )

        async with factory() as session:
            session.add(
                Booking(
                    reference=uuid4().hex.upper(),
                    hotel_id=DEMO_HOTEL_ID,
                    room_id=room_id,
                    guest_name="Second Guest",
                    guest_count=1,
                    check_in_date=check_in + timedelta(days=1),
                    check_out_date=check_out + timedelta(days=1),
                )
            )
            with pytest.raises(IntegrityError) as error:
                await session.flush()
            assert error.value.orig is not None
            constraint_name = getattr(
                error.value.orig.__cause__,
                "constraint_name",
                None,
            )
            assert constraint_name == BOOKING_OVERLAP_CONSTRAINT
            await session.rollback()
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_booking_known_errors_and_validation() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    transport = httpx.ASGITransport(app=app)
    check_in = date.today() + timedelta(days=2)
    check_out = check_in + timedelta(days=1)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/seed")
            unknown_hotel = await client.post(
                "/api/v1/bookings",
                json=booking_payload(
                    check_in=check_in,
                    check_out=check_out,
                    hotel_id=str(uuid4()),
                ),
            )
            invalid_dates = await client.post(
                "/api/v1/bookings",
                json=booking_payload(check_in=check_in, check_out=check_in),
            )
            unknown_booking = await client.get(
                "/api/v1/bookings/00000000000000000000000000000000"
            )
            malformed_reference = await client.get("/api/v1/bookings/not-a-reference")

            assert unknown_hotel.status_code == 404
            assert unknown_hotel.json()["code"] == "hotel_not_found"
            assert invalid_dates.status_code == 400
            assert invalid_dates.json()["code"] == "invalid_date_range"
            assert unknown_booking.status_code == 404
            assert unknown_booking.json()["code"] == "booking_not_found"
            assert malformed_reference.status_code == 422
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()
