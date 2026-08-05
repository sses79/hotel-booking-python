"""Stable API problem response schemas."""

from pydantic import BaseModel


class ProblemResponse(BaseModel):
    """Machine-readable code plus a human-readable failure description."""

    code: str
    message: str
    details: dict[str, str] | None = None
