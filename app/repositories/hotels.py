"""Hotel lookup and room availability queries."""

from datetime import date
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking, Hotel, Room, RoomType


async def find_hotel_by_name(session: AsyncSession, name: str) -> Hotel | None:
    """Find one hotel by its exact unique name."""

    statement = select(Hotel).where(Hotel.name == name)
    hotels = await session.scalars(statement)
    return hotels.one_or_none()


async def find_hotel_by_id(session: AsyncSession, hotel_id: UUID) -> Hotel | None:
    """Find one hotel by its primary key."""

    return await session.get(Hotel, hotel_id)


async def list_available_rooms(
    session: AsyncSession,
    *,
    hotel_id: UUID,
    check_in_date: date,
    check_out_date: date,
    guests: int,
    room_type: RoomType | None,
) -> list[Room]:
    """Return suitable rooms without a booking that overlaps the requested stay."""

    overlapping_booking = exists().where(
        Booking.room_id == Room.id,
        Booking.check_in_date < check_out_date,
        check_in_date < Booking.check_out_date,
    )
    statement = select(Room).where(
        Room.hotel_id == hotel_id,
        Room.capacity >= guests,
        ~overlapping_booking,
    )
    if room_type is not None:
        statement = statement.where(Room.room_type == room_type)

    statement = statement.order_by(
        Room.capacity,
        Room.room_type,
        Room.room_number,
    )
    return list(await session.scalars(statement))
