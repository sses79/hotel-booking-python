"""FastAPI dependencies shared by route modules."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide one SQLAlchemy session per request and close it afterward."""

    factory = cast(
        async_sessionmaker[AsyncSession],
        request.app.state.db_session_factory,
    )
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
