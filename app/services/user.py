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


async def resolve_user_by_phone(
    session: AsyncSession,
    phone_number: str,
    first_name: str = "",
) -> User:
    """
    Find existing user by WhatsApp phone number or telegram_id matching that phone,
    or create a new one. Used by both WhatsApp webhook and manual registration.

    Phone number should be in international format without '+' (e.g., "593987654321").
    """
    # Normalize: strip leading '+' if present
    phone = phone_number.lstrip("+")

    # Search by whatsapp_id first
    result = await session.execute(
        select(User).where(User.whatsapp_id == phone)
    )
    user = result.scalar_one_or_none()

    if user:
        logger.debug("Found existing user for whatsapp_id=%s", phone)
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        return user

    # Try matching by telegram_id (user might have linked accounts)
    # For now, create a new user — linking comes in Fase 3 (user account merging)
    logger.info("Creating new user for WhatsApp phone=%s", phone)
    user = User(
        whatsapp_id=phone,
        first_name=first_name or "Usuario WA",
    )
    session.add(user)
    return user
