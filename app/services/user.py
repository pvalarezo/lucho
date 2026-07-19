"""User service — resolve or create users from chat platform IDs.

Also handles subscription creation for new users (trial).
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import SubscriptionPlan

logger = logging.getLogger(__name__)


async def resolve_user_by_telegram(
    session: AsyncSession,
    telegram_id: str,
    first_name: str = "",
    last_name: str | None = None,
) -> User:
    """
    Find existing user by telegram_id or create a new one.
    New users get a trial subscription to the 'basic' plan.
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
        is_active=True,  # new users can talk immediately (trial)
    )
    session.add(user)
    await session.flush()

    # Create trial subscription
    await _create_trial_subscription(session, user)

    return user


async def resolve_user_by_phone(
    session: AsyncSession,
    phone_number: str,
    first_name: str = "",
) -> User:
    """
    Find existing user by WhatsApp phone number or telegram_id matching that phone,
    or create a new one. New users get a trial subscription.
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

    logger.info("Creating new user for WhatsApp phone=%s", phone)
    user = User(
        whatsapp_id=phone,
        first_name=first_name or "Usuario WA",
        is_active=True,  # new users can talk immediately (trial)
    )
    session.add(user)
    await session.flush()

    # Create trial subscription
    await _create_trial_subscription(session, user)

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


async def get_user_with_subscription(
    session: AsyncSession,
    user_id: str,
) -> User | None:
    """
    Fetch a user with their subscription and plan eagerly loaded.
    Use this when you need to check access.
    """
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(User)
        .options(
            selectinload(User.subscription).selectinload(Subscription.plan_ref),
            selectinload(User.profile),
        )
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


# =============================================================================
# SUBSCRIPTION HELPERS
# =============================================================================


async def _create_trial_subscription(
    session: AsyncSession,
    user: User,
) -> Subscription:
    """
    Create a trial subscription for a new user.
    Finds the 'basic' plan and creates a subscription with trial status.
    """
    # Find the basic plan
    result = await session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.slug == "basic")
    )
    plan = result.scalar_one_or_none()

    if not plan:
        logger.warning(
            "No 'basic' plan found in subscription_plans — "
            "creating subscription without plan. Run seed_subscription_plans.py first."
        )
        # Fallback: use a hardcoded trial
        sub = Subscription(
            user_id=user.id,
            status=SubscriptionStatus.trial,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        session.add(sub)
        return sub

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.trial,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=plan.trial_days),
    )
    session.add(sub)
    logger.info(
        "Created trial subscription for user=%s (plan=%s, trial_ends=%s)",
        user.id,
        plan.name,
        sub.trial_ends_at,
    )
    return sub


async def _ensure_trial_subscription(
    session: AsyncSession,
    user_id: str,
) -> Subscription | None:
    """
    Ensure a user has a trial subscription. Creates one if missing.
    Used by check_access for users without subscriptions.
    """
    from app.models.user import User as UserModel

    result = await session.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    return await _create_trial_subscription(session, user)


# =============================================================================
# ACCESS CHECK
# =============================================================================


class AccessResult:
    """Result of an access check."""

    def __init__(self, allowed: bool, reason: str | None = None):
        self.allowed = allowed
        self.reason = reason


async def check_access(session: AsyncSession, user_id: str) -> AccessResult:
    """
    Check whether a user is allowed to interact with Lucho.

    Returns AccessResult with:
    - allowed: True if the user can proceed
    - reason: human-readable explanation if denied (Spanish)
    """
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan_ref))
        .where(Subscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()

    if not sub:
        # No subscription found — create a trial for this user
        logger.warning("User %s has no subscription — creating trial", user_id)
        sub = await _ensure_trial_subscription(session, user_id)
        if sub:
            return AccessResult(allowed=True)
        return AccessResult(
            allowed=False,
            reason="⚠️ No tenés una suscripción activa. Contactanos para activar tu cuenta.",
        )

    now = datetime.now(timezone.utc)

    # Active subscription — always allowed
    if sub.status == SubscriptionStatus.active:
        return AccessResult(allowed=True)

    # Trial — check expiry
    if sub.status == SubscriptionStatus.trial:
        if sub.trial_ends_at and sub.trial_ends_at > now:
            return AccessResult(allowed=True)
        # Trial expired → mark as expired
        sub.status = SubscriptionStatus.expired
        await session.flush()
        return AccessResult(
            allowed=False,
            reason=(
                "⏰ *Tu período de prueba de 7 días terminó.*\n\n"
                "Para seguir usando Lucho, elegí tu plan:\n"
                "• Plan Básico — $X/mes\n\n"
                "Pronto podrás suscribirte con tarjeta, depósito o transferencia."
            ),
        )

    # Expired or cancelled
    if sub.status in (SubscriptionStatus.expired, SubscriptionStatus.cancelled):
        return AccessResult(
            allowed=False,
            reason=(
                "🔒 *Tu suscripción está inactiva.*\n\n"
                "Renová tu plan para seguir usando Lucho."
            ),
        )

    # Unknown status — deny by default
    return AccessResult(
        allowed=False,
        reason="⚠️ No pudimos verificar tu suscripción. Contactanos.",
    )
