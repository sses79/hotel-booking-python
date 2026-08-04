"""FastAPI application factory and ASGI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine


def create_app(
    settings: Settings | None = None,
    *,
    db_engine: AsyncEngine | None = None,
) -> FastAPI:
    """Create an independently configurable application instance."""

    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)
    engine = db_engine or create_engine(runtime_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        await application.state.db_engine.dispose()

    application = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.db_engine = engine
    application.include_router(health_router)
    return application


app = create_app()
