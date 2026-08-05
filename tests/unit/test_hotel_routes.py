"""Hotel route contract tests."""

from app.core.config import Settings
from app.main import create_app


def test_openapi_exposes_hotel_lookup_and_availability() -> None:
    app = create_app(Settings(app_env="prod"))

    paths = app.openapi()["paths"]

    assert "/api/v1/hotels" in paths
    assert "/api/v1/hotels/{hotel_id}/rooms/available" in paths
