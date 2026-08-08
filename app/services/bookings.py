"""Booking creation and lookup use cases."""

import secrets
from typing import cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.db.models import BOOKING_OVERLAP_CONSTRAINT, Booking
from app.repositories import bookings as booking_repository
from app.repositories import hotels as hotel_repository
from app.schemas.bookings import BookingCreate
from app.services.hotels import validate_stay_dates


def generate_booking_reference() -> str:
    """Generate an unguessable 128-bit uppercase hexadecimal reference."""

    return secrets.token_hex(16).upper()


def _constraint_name(error: IntegrityError) -> str | None:
    """Read PostgreSQL's constraint name from SQLAlchemy's wrapped exception."""

    if error.orig is None or error.orig.__cause__ is None:
        return None
    return cast(
        str | None,
        getattr(error.orig.__cause__, "constraint_name", None),
    )


async def create_booking(
    session: AsyncSession,
    request: BookingCreate,
) -> Booking:
    """Select and reserve one suitable room inside the caller's transaction."""

    hotel = await hotel_repository.find_hotel_by_id(session, request.hotel_id)
    if hotel is None:
        raise NotFoundError(
            code="hotel_not_found",
            message="Hotel not found",
            details={"hotel_id": str(request.hotel_id)},
        )

    validate_stay_dates(request.check_in_date, request.check_out_date)
    room = await booking_repository.select_room_for_booking(
        session,
        hotel_id=request.hotel_id,
        check_in_date=request.check_in_date,
        check_out_date=request.check_out_date,
        guests=request.guest_count,
        room_type=request.room_type,
    )
    if room is None:
        raise ConflictError(
            code="no_room_available",
            message="No suitable room is available for the requested stay",
        )

    booking = Booking(
        reference=generate_booking_reference(),
        hotel_id=request.hotel_id,
        room_id=room.id,
        guest_name=request.guest_name,
        guest_count=request.guest_count,
        check_in_date=request.check_in_date,
        check_out_date=request.check_out_date,
    )
    session.add(booking)
    try:
        await session.flush()
    except IntegrityError as error:
        if _constraint_name(error) == BOOKING_OVERLAP_CONSTRAINT:
            raise ConflictError(
                code="no_room_available",
                message="No suitable room is available for the requested stay",
            ) from error
        raise
    return booking


async def get_booking_by_reference(
    session: AsyncSession,
    reference: str,
) -> Booking:
    """Return one public booking or raise a known not-found error."""

    booking = await booking_repository.find_booking_by_reference(session, reference)
    if booking is None:
        raise NotFoundError(
            code="booking_not_found",
            message="Booking not found",
            details={"reference": reference},
        )
    return booking
