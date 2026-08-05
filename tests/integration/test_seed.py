"""PostgreSQL-backed seed, reset, and constraint tests."""

import asyncio
from datetime import date
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.models import Booking, Hotel, Room, RoomType
from app.main import create_app
from app.services.seed import DEMO_HOTEL_ID
from tests.integration.conftest import integration_database_url, session_factory_for

pytestmark = pytest.mark.integration


async def table_counts(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int, int]:
    """Count all Phase 2 entities."""

    async with factory() as session:
        hotels = await session.scalar(select(func.count()).select_from(Hotel))
        rooms = await session.scalar(select(func.count()).select_from(Room))
        bookings = await session.scalar(select(func.count()).select_from(Booking))
    return int(hotels or 0), int(rooms or 0), int(bookings or 0)


@pytest.mark.asyncio
async def test_seed_is_repeatable_and_reset_removes_all_data() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    factory = session_factory_for(app)
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            first = await client.post("/api/v1/admin/seed")
            second = await client.post("/api/v1/admin/seed")

            assert first.status_code == 200
            assert second.status_code == 200
            assert (
                first.json()
                == second.json()
                == {
                    "hotel_id": str(DEMO_HOTEL_ID),
                    "hotel_name": "Grand Plaza Hotel",
                    "rooms_created": 6,
                }
            )
            assert await table_counts(factory) == (1, 6, 0)

            reset = await client.post("/api/v1/admin/reset")

            assert reset.status_code == 204
            assert reset.content == b""
            assert await table_counts(factory) == (0, 0, 0)
    finally:
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_seed_requests_are_serialized() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    factory = session_factory_for(app)
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            responses = await asyncio.gather(
                client.post("/api/v1/admin/seed"),
                client.post("/api/v1/admin/seed"),
            )

            assert [response.status_code for response in responses] == [200, 200]
            assert responses[0].json() == responses[1].json()
            assert await table_counts(factory) == (1, 6, 0)
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_database_rejects_non_positive_room_capacity() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    factory = session_factory_for(app)
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            seeded = await client.post("/api/v1/admin/seed")
            assert seeded.status_code == 200

        async with factory() as session:
            session.add(
                Room(
                    id=uuid4(),
                    hotel_id=UUID(seeded.json()["hotel_id"]),
                    room_number="INVALID",
                    room_type=RoomType.SINGLE,
                    capacity=0,
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
async def test_database_rejects_booking_for_room_in_another_hotel() -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    factory = session_factory_for(app)
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            seeded = await client.post("/api/v1/admin/seed")
            assert seeded.status_code == 200

        async with factory() as session:
            room_id = await session.scalar(select(Room.id).limit(1))
            assert room_id is not None
            other_hotel = Hotel(id=uuid4(), name="Other Hotel")
            session.add(other_hotel)
            await session.flush()
            session.add(
                Booking(
                    id=uuid4(),
                    reference=uuid4().hex.upper(),
                    hotel_id=other_hotel.id,
                    room_id=room_id,
                    guest_name="Cross-hotel Test",
                    guest_count=1,
                    check_in_date=date(2026, 9, 1),
                    check_out_date=date(2026, 9, 2),
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("guest_count", "check_in_date", "check_out_date"),
    [
        (0, date(2026, 9, 1), date(2026, 9, 2)),
        (1, date(2026, 9, 1), date(2026, 9, 1)),
    ],
)
async def test_database_rejects_invalid_booking_values(
    guest_count: int,
    check_in_date: date,
    check_out_date: date,
) -> None:
    app = create_app(Settings(app_env="test", database_url=integration_database_url()))
    factory = session_factory_for(app)
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            seeded = await client.post("/api/v1/admin/seed")
            assert seeded.status_code == 200

        async with factory() as session:
            room_id = await session.scalar(select(Room.id).limit(1))
            assert room_id is not None
            session.add(
                Booking(
                    id=uuid4(),
                    reference=uuid4().hex.upper(),
                    hotel_id=DEMO_HOTEL_ID,
                    room_id=room_id,
                    guest_name="Constraint Test",
                    guest_count=guest_count,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
    finally:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            await client.post("/api/v1/admin/reset")
        await app.state.db_engine.dispose()
