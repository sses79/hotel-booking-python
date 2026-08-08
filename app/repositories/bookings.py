"""Transactional room selection and booking lookup queries."""

from datetime import date
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking, Room, RoomType


async def select_room_for_booking(
    session: AsyncSession,
    *,
    hotel_id: UUID,
    check_in_date: date,
    check_out_date: date,
    guests: int,
    room_type: RoomType | None,
) -> Room | None:
    """Lock and return the first suitable room without an overlapping booking."""

    overlapping_booking = exists().where(
        Booking.room_id == Room.id,
        Booking.check_in_date < check_out_date,
        check_in_date < Booking.check_out_date,
    )
    statement = (
        select(Room)
        .where(
            Room.hotel_id == hotel_id,
            Room.capacity >= guests,
            ~overlapping_booking,
        )
        .order_by(Room.capacity, Room.room_type, Room.room_number)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if room_type is not None:
        statement = statement.where(Room.room_type == room_type)

    rooms = await session.scalars(statement)
    return rooms.one_or_none()


async def find_booking_by_reference(
    session: AsyncSession,
    reference: str,
) -> Booking | None:
    """Find one booking by its unique public reference."""

    statement = select(Booking).where(Booking.reference == reference)
    bookings = await session.scalars(statement)
    return bookings.one_or_none()
