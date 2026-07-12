"""User service — resolve or create users from chat platform IDs."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


async def resolve_user_by_telegram(
    session: AsyncSession,
    telegram_id: str,
    first_name: str = "",
    last_name: str | None = None,
) -> User:
    """
    Find existing user by telegram_id or create a new one.
    Returns the User ORM instance (not yet committed — caller flushes).
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user:
        logger.debug("Found existing user for telegram_id=%s", telegram_id)
        # Update name if changed
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        if last_name and user.last_name != last_name:
            user.last_name = last_name
        return user

    logger.info("Creating new user for telegram_id=%s", telegram_id)
    user = User(
        telegram_id=telegram_id,
        first_name=first_name or "Usuario",
        last_name=last_name,
    )
    session.add(user)
    return user


async def get_user_by_id(
    session: AsyncSession,
    user_id: str,
) -> User | None:
    """Fetch a user by UUID string."""
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()
