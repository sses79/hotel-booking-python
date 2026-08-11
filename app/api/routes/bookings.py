"""Booking creation and public-reference lookup endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Path, Response, status

from app.api.dependencies import SessionDep
from app.schemas.bookings import BookingCreate, BookingResponse
from app.schemas.errors import ProblemResponse
from app.services.bookings import create_booking, get_booking_by_reference

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])

problem_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
    status.HTTP_409_CONFLICT: {"model": ProblemResponse},
}


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses,
)
async def book_room(
    request: BookingCreate,
    session: SessionDep,
    response: Response,
) -> BookingResponse:
    """Reserve one suitable room for the requested stay."""

    async with session.begin():
        booking = await create_booking(session, request)

    response.headers["Location"] = f"/api/v1/bookings/{booking.reference}"
    return BookingResponse.model_validate(booking)


@router.get(
    "/{reference}",
    response_model=BookingResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ProblemResponse}},
)
async def find_booking(
    session: SessionDep,
    reference: Annotated[
        str,
        Path(min_length=32, max_length=32, pattern=r"^[A-F0-9]{32}$"),
    ],
) -> BookingResponse:
    """Find a booking by its public reference."""

    booking = await get_booking_by_reference(session, reference)
    return BookingResponse.model_validate(booking)
