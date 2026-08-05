"""Hotel lookup and room availability endpoints."""

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import SessionDep
from app.db.models import RoomType
from app.schemas.errors import ProblemResponse
from app.schemas.hotels import AvailableRoomResponse, HotelResponse
from app.services.hotels import get_available_rooms, get_hotel_by_name

router = APIRouter(prefix="/api/v1/hotels", tags=["hotels"])

problem_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ProblemResponse},
    status.HTTP_404_NOT_FOUND: {"model": ProblemResponse},
}


@router.get("", response_model=HotelResponse, responses=problem_responses)
async def find_hotel(
    session: SessionDep,
    name: Annotated[str, Query(min_length=1, max_length=200)],
) -> HotelResponse:
    """Find a hotel by its exact name."""

    hotel = await get_hotel_by_name(session, name)
    return HotelResponse.model_validate(hotel)


@router.get(
    "/{hotel_id}/rooms/available",
    response_model=list[AvailableRoomResponse],
    responses=problem_responses,
)
async def find_available_rooms(
    session: SessionDep,
    hotel_id: UUID,
    check_in: date,
    check_out: date,
    guests: Annotated[int, Query(ge=1)],
    room_type: RoomType | None = None,
) -> list[AvailableRoomResponse]:
    """Find suitable rooms free for the requested half-open date range."""

    rooms = await get_available_rooms(
        session,
        hotel_id=hotel_id,
        check_in_date=check_in,
        check_out_date=check_out,
        guests=guests,
        room_type=room_type,
    )
    return [AvailableRoomResponse.model_validate(room) for room in rooms]
