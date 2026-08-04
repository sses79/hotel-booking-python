"""Deterministic demo seed and reset operations."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking, Hotel, Room, RoomType

DEMO_HOTEL_ID = UUID("00000000-0000-0000-0000-000000000001")
DEMO_HOTEL_NAME = "Grand Plaza Hotel"


@dataclass(frozen=True)
class RoomSeed:
    """One stable room in the demo dataset."""

    id: UUID
    room_number: str
    room_type: RoomType
    capacity: int


DEMO_ROOMS = (
    RoomSeed(
        id=UUID("00000000-0000-0000-0000-000000000101"),
        room_number="101",
        room_type=RoomType.SINGLE,
        capacity=1,
    ),
    RoomSeed(
        id=UUID("00000000-0000-0000-0000-000000000102"),
        room_number="102",
        room_type=RoomType.SINGLE,
        capacity=1,
    ),
    RoomSeed(
        id=UUID("00000000-0000-0000-0000-000000000201"),
        room_number="201",
        room_type=RoomType.DOUBLE,
        capacity=2,
    ),
    RoomSeed(
        id=UUID("00000000-0000-0000-0000-000000000202"),
        room_number="202",
        room_type=RoomType.DOUBLE,
        capacity=2,
    ),
    RoomSeed(
        id=UUID("00000000-0000-0000-0000-000000000301"),
        room_number="301",
        room_type=RoomType.DELUXE,
        capacity=4,
    ),
    RoomSeed(
        id=UUID("00000000-0000-0000-0000-000000000302"),
        room_number="302",
        room_type=RoomType.DELUXE,
        capacity=4,
    ),
)


@dataclass(frozen=True)
class SeedSummary:
    """Result returned after rebuilding the demo dataset."""

    hotel_id: UUID
    hotel_name: str
    rooms_created: int


async def reset_data(session: AsyncSession) -> None:
    """Delete application data in foreign-key dependency order."""

    await session.execute(delete(Booking))
    await session.execute(delete(Room))
    await session.execute(delete(Hotel))


async def seed_demo_data(session: AsyncSession) -> SeedSummary:
    """Reset and recreate the stable Phase 2 demo dataset."""

    await reset_data(session)

    hotel = Hotel(
        id=DEMO_HOTEL_ID,
        name=DEMO_HOTEL_NAME,
        rooms=[
            Room(
                id=room.id,
                room_number=room.room_number,
                room_type=room.room_type,
                capacity=room.capacity,
            )
            for room in DEMO_ROOMS
        ],
    )
    session.add(hotel)
    await session.flush()

    return SeedSummary(
        hotel_id=hotel.id,
        hotel_name=hotel.name,
        rooms_created=len(DEMO_ROOMS),
    )
