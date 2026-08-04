"""Environment gating for destructive admin routes."""

import pytest

from app.core.config import AppEnvironment, Settings
from app.main import create_app


def route_paths(app_env: AppEnvironment) -> set[str]:
    """Build an app and return its registered route paths."""

    app = create_app(Settings(app_env=app_env))
    return set(app.openapi()["paths"])


def test_admin_routes_are_available_locally() -> None:
    paths = route_paths("local")

    assert "/api/v1/admin/seed" in paths
    assert "/api/v1/admin/reset" in paths


@pytest.mark.parametrize("app_env", ["dev", "prod"])
def test_admin_routes_are_hidden_outside_local_and_test(
    app_env: AppEnvironment,
) -> None:
    paths = route_paths(app_env)

    assert "/api/v1/admin/seed" not in paths
    assert "/api/v1/admin/reset" not in paths
