"""Booking route contract tests."""

from app.core.config import Settings
from app.main import create_app


def test_openapi_exposes_booking_creation_and_lookup() -> None:
    app = create_app(Settings(app_env="prod"))

    paths = app.openapi()["paths"]

    assert "/api/v1/bookings" in paths
    assert "/api/v1/bookings/{reference}" in paths
