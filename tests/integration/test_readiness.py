"""PostgreSQL-backed readiness test."""

import os

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_readiness_with_postgres() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    app = create_app(Settings(app_env="test", database_url=database_url))
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/health/ready")
    finally:
        await app.state.db_engine.dispose()

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
