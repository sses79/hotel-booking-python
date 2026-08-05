"""Hotel lookup and room availability use cases."""

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.db.models import Hotel, Room, RoomType
from app.repositories import hotels as hotel_repository


def validate_stay_dates(
    check_in_date: date,
    check_out_date: date,
    *,
    today: date | None = None,
) -> None:
    """Validate the cross-field rules for a requested stay."""

    current_date = today or date.today()
    if check_in_date < current_date:
        raise BadRequestError(
            code="check_in_in_past",
            message="Check-in date must be today or later",
            details={"check_in": check_in_date.isoformat()},
        )
    if check_out_date <= check_in_date:
        raise BadRequestError(
            code="invalid_date_range",
            message="Check-out date must be after check-in date",
            details={
                "check_in": check_in_date.isoformat(),
                "check_out": check_out_date.isoformat(),
            },
        )


async def get_hotel_by_name(session: AsyncSession, name: str) -> Hotel:
    """Return an exact hotel-name match or raise a known error."""

    normalized_name = name.strip()
    if not normalized_name:
        raise BadRequestError(
            code="invalid_hotel_name",
            message="Hotel name must not be blank",
        )

    hotel = await hotel_repository.find_hotel_by_name(session, normalized_name)
    if hotel is None:
        raise NotFoundError(
            code="hotel_not_found",
            message="Hotel not found",
            details={"name": normalized_name},
        )
    return hotel


async def get_available_rooms(
    session: AsyncSession,
    *,
    hotel_id: UUID,
    check_in_date: date,
    check_out_date: date,
    guests: int,
    room_type: RoomType | None,
) -> list[Room]:
    """Return rooms suitable and free for the requested half-open date range."""

    validate_stay_dates(check_in_date, check_out_date)
    hotel = await hotel_repository.find_hotel_by_id(session, hotel_id)
    if hotel is None:
        raise NotFoundError(
            code="hotel_not_found",
            message="Hotel not found",
            details={"hotel_id": str(hotel_id)},
        )

    return await hotel_repository.list_available_rooms(
        session,
        hotel_id=hotel_id,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        guests=guests,
        room_type=room_type,
    )
