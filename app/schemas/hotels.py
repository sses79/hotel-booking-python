"""Hotel lookup and room availability response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import RoomType


class HotelResponse(BaseModel):
    """Public hotel representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime


class AvailableRoomResponse(BaseModel):
    """A room that can host the requested stay and guest count."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hotel_id: UUID
    room_number: str
    room_type: RoomType
    capacity: int
