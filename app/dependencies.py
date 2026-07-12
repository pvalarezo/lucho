"""Dependency injection — FastAPI dependencies for DB session, etc."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, closed after the request."""
    async with async_session() as session:
        yield session
