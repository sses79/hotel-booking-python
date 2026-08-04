"""Health route unit tests."""

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_liveness() -> None:
    app = create_app(Settings(app_env="test"))
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/health/live")
    finally:
        await app.state.db_engine.dispose()

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_openapi_exposes_health_routes() -> None:
    app = create_app(Settings(app_env="test"))
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get("/openapi.json")
    finally:
        await app.state.db_engine.dispose()

    assert response.status_code == 200
    document = response.json()
    assert "/health/live" in document["paths"]
    assert "/health/ready" in document["paths"]
