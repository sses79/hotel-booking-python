"""Local and test-only data management routes."""

from fastapi import APIRouter, Response, status

from app.api.dependencies import SessionDep
from app.schemas.admin import SeedResponse
from app.services.seed import reset_data, seed_demo_data

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/seed", response_model=SeedResponse)
async def seed(session: SessionDep) -> SeedResponse:
    """Reset and recreate the deterministic demo dataset."""

    async with session.begin():
        summary = await seed_demo_data(session)

    return SeedResponse(
        hotel_id=summary.hotel_id,
        hotel_name=summary.hotel_name,
        rooms_created=summary.rooms_created,
    )


@router.post(
    "/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def reset(session: SessionDep) -> Response:
    """Delete all application data."""

    async with session.begin():
        await reset_data(session)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
