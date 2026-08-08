"""Booking creation and lookup API schemas."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.models import RoomType

type GuestName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class BookingCreate(BaseModel):
    """Information required to reserve one suitable room."""

    hotel_id: UUID
    guest_name: GuestName
    guest_count: int = Field(ge=1)
    check_in_date: date
    check_out_date: date
    room_type: RoomType | None = None


class BookingResponse(BaseModel):
    """Public booking representation returned after create and lookup."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference: str
    hotel_id: UUID
    room_id: UUID
    guest_name: str
    guest_count: int
    check_in_date: date
    check_out_date: date
    created_at: datetime
