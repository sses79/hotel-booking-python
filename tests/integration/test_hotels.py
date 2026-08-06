"""PostgreSQL-backed hotel lookup and room availability tests."""

from datetime import date, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Booking, Room
from app.main import create_app
from app.services.seed import DEMO_HOTEL_ID
from tests.integration.conftest import integration_database_url, session_factory_for

pytestmark = pytest.mark.integration


def availability_path(
    hotel_id: UUID,
    *,
    check_in: date,
    check_out: date,
    guests: int,
    room_type: str | None = None,
) -> str:
    """Build an availability URL with ISO date query parameters."""

    path = (
        f"/api/v1/hotels/{hotel_id}/rooms/available"
        f"?check_in={check_in.isoformat()}"
        f"&check_out={check_out.isoformat()}"
        f"&guests={guests}"
    )
    if room_type is not None:
        path += f"&room_type={room_type}"
    return path


@pytest.mark.asyncio
async def test_hotel_lookup_and_unknown_problem_response() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            seeded = await client.post("/api/v1/admin/seed")
            found = await client.get(
                "/api/v1/hotels",
                params={"name": "Grand Plaza Hotel"},
            )
            unknown = await client.get(
                "/api/v1/hotels",
                params={"name": "Unknown Hotel"},
            )

            assert seeded.status_code == 200
            assert found.status_code == 200
            assert found.json()["id"] == str(DEMO_HOTEL_ID)
            assert found.json()["name"] == "Grand Plaza Hotel"
            assert "created_at" in found.json()
            assert unknown.status_code == 404
            assert unknown.json() == {
                "code": "hotel_not_found",
                "message": "Hotel not found",
                "details": {"name": "Unknown Hotel"},
            }
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_availability_filters_capacity_type_and_orders_smallest_first() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    transport = httpx.ASGITransport(app=app)
    check_in = date.today() + timedelta(days=1)
    check_out = check_in + timedelta(days=2)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            seeded = await client.post("/api/v1/admin/seed")
            available = await client.get(
                availability_path(
                    DEMO_HOTEL_ID,
                    check_in=check_in,
                    check_out=check_out,
                    guests=2,
                )
            )
            deluxe = await client.get(
                availability_path(
                    DEMO_HOTEL_ID,
                    check_in=check_in,
                    check_out=check_out,
                    guests=2,
                    room_type="deluxe",
                )
            )
            invalid_guests = await client.get(
                availability_path(
                    DEMO_HOTEL_ID,
                    check_in=check_in,
                    check_out=check_out,
                    guests=0,
                )
            )

            assert seeded.status_code == 200
            assert available.status_code == 200
            assert [room["room_number"] for room in available.json()] == [
                "201",
                "202",
                "301",
                "302",
            ]
            assert [room["room_number"] for room in deluxe.json()] == ["301", "302"]
            assert invalid_guests.status_code == 422
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_availability_uses_half_open_dates_and_maps_known_errors() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    factory = session_factory_for(app)
    transport = httpx.ASGITransport(app=app)
    booked_check_in = date.today() + timedelta(days=2)
    booked_check_out = booked_check_in + timedelta(days=2)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            seeded = await client.post("/api/v1/admin/seed")
            assert seeded.status_code == 200

            async with factory.begin() as session:
                room_id = await session.scalar(
                    select(Room.id).where(Room.room_number == "201")
                )
                assert room_id is not None
                session.add(
                    Booking(
                        reference=uuid4().hex.upper(),
                        hotel_id=DEMO_HOTEL_ID,
                        room_id=room_id,
                        guest_name="Availability Test",
                        guest_count=2,
                        check_in_date=booked_check_in,
                        check_out_date=booked_check_out,
                    )
                )

            overlapping = await client.get(
                availability_path(
                    DEMO_HOTEL_ID,
                    check_in=booked_check_in + timedelta(days=1),
                    check_out=booked_check_out + timedelta(days=1),
                    guests=2,
                )
            )
            back_to_back = await client.get(
                availability_path(
                    DEMO_HOTEL_ID,
                    check_in=booked_check_out,
                    check_out=booked_check_out + timedelta(days=1),
                    guests=2,
                )
            )
            invalid_dates = await client.get(
                availability_path(
                    DEMO_HOTEL_ID,
                    check_in=booked_check_in,
                    check_out=booked_check_in,
                    guests=2,
                )
            )
            unknown_hotel_with_invalid_dates = await client.get(
                availability_path(
                    uuid4(),
                    check_in=booked_check_in,
                    check_out=booked_check_in,
                    guests=2,
                )
            )

            assert overlapping.status_code == 200
            assert "201" not in [room["room_number"] for room in overlapping.json()]
            assert back_to_back.status_code == 200
            assert "201" in [room["room_number"] for room in back_to_back.json()]
            assert invalid_dates.status_code == 400
            assert invalid_dates.json()["code"] == "invalid_date_range"
            assert unknown_hotel_with_invalid_dates.status_code == 404
            assert unknown_hotel_with_invalid_dates.json()["code"] == "hotel_not_found"
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()
