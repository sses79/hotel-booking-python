"""Admin operation response schemas."""

from uuid import UUID

from pydantic import BaseModel


class SeedResponse(BaseModel):
    """Summary of the deterministic demo dataset."""

    hotel_id: UUID
    hotel_name: str
    rooms_created: int
