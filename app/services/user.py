"""User service — resolve or create users from chat platform IDs.

Also handles subscription creation for new users (trial).
"""

import logging
from datetime import datetime, timedelta

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
            trial_ends_at=datetime.now() + timedelta(days=7),
        )
        session.add(sub)
        return sub

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        status=SubscriptionStatus.trial,
        trial_ends_at=datetime.now() + timedelta(days=plan.trial_days),
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

    now = datetime.now()

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
                "Elegí tu plan para seguir usando Lucho:\n"
                "📦 *Básico* — $4.99/mes\n"
                "   • 2 vehículos, 10 docs, 3 proyectos\n"
                "📦 *Premium* — $9.99/mes\n"
                "   • 4 vehículos, 50 docs, 10 proyectos\n"
                "   • Soporte prioritario\n"
                "📦 *Familia* — $14.99/mes\n"
                "   • Todo ilimitado + modo cuidado\n\n"
                "Escribime 'suscribirme' al +593 98 422 3245 y te ayudo con el pago."
            ),
        )

    # Expired or cancelled
    if sub.status in (SubscriptionStatus.expired, SubscriptionStatus.cancelled):
        plan_name = sub.plan_ref.name if sub.plan_ref else "tu plan"
        price = float(sub.plan_ref.price_monthly_usd) if sub.plan_ref else 4.99
        return AccessResult(
            allowed=False,
            reason=(
                f"⏰ *Tu suscripción a Lucho está inactiva.*\n\n"
                f"Tu plan {plan_name} (${price:.2f}/mes) expiró.\n\n"
                f"Pero no te preocupes — ¡tus datos están seguros!\n"
                f"Renová en 1 minuto y seguís donde estabas:\n\n"
                f"Escribime *'renovar'* o *'suscribirme'* y te paso el link. 📱"
            ),
        )

    # Unknown status — deny by default
    return AccessResult(
        allowed=False,
        reason="⚠️ No pudimos verificar tu suscripción. Contactanos.",
    )


# =============================================================================
# POST-PAGO FLOW
# =============================================================================


async def _get_post_pago_step(session: AsyncSession, user_id: str) -> int | None:
    """
    Determine which post-pago step the user is on.
    Uses onboarding_step: 3=cédula, 4=email, 5=full_name, 6=privacy, 7=done.
    Returns None if post-pago already completed.
    """
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None

    step = user.onboarding_step
    if step < 3:
        # Trial just expired, start post-pago at step 3 (cédula)
        return 3
    if 3 <= step <= 6:
        # Mid-post-pago, resume at current step
        return step
    # step >= 7: completed
    return None


async def advance_post_pago_step(
    session: AsyncSession,
    user_id: str,
    expected_step: int,
    user_input: str,
) -> dict:
    """
    Process one post-pago step, saving data to UserProfile.
    Returns dict with {ok: bool, next_step: int | None, message: str}.
    """
    from app.models.user_profile import UserProfile

    # Validate user exists
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return {"ok": False, "next_step": None, "message": "Error: usuario no encontrado."}

    # Get or create profile
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserProfile(user_id=user_id)
        session.add(profile)

    text = user_input.strip()

    if expected_step == 3:
        # Step 3: cédula/RUC
        if len(text) < 6 or len(text) > 13:
            return {
                "ok": False,
                "next_step": 3,
                "message": "Eso no parece un número de cédula o RUC válido. Intentá de nuevo.",
            }
        profile.id_number = text
        user.onboarding_step = 4
        await session.flush()
        return {
            "ok": True,
            "next_step": 4,
            "message": (
                f"✅ Cédula *{text}* registrada.\n\n"
                "¿Cuál es tu correo electrónico?"
            ),
        }

    elif expected_step == 4:
        # Step 4: email
        if "@" not in text or "." not in text.split("@")[-1]:
            return {
                "ok": False,
                "next_step": 4,
                "message": "Eso no parece un correo válido. Ponelo de nuevo.",
            }
        profile.email = text
        user.onboarding_step = 5
        await session.flush()
        return {
            "ok": True,
            "next_step": 5,
            "message": (
                f"✅ Correo *{text}* registrado.\n\n"
                "¿Cuál es tu nombre completo (como aparece en tu cédula)?"
            ),
        }

    elif expected_step == 5:
        # Step 5: full name
        if len(text) < 5:
            return {
                "ok": False,
                "next_step": 5,
                "message": "Ese nombre es muy corto. Poné tu nombre completo.",
            }
        profile.full_name = text
        user.onboarding_step = 6
        await session.flush()
        return {
            "ok": True,
            "next_step": 6,
            "message": (
                f"✅ Nombre *{text}* registrado.\n\n"
                "Antes de continuar, revisá nuestras políticas de privacidad "
                "en: https://auracore.com/politicas\n\n"
                "Respondé *SI* para aceptar y continuar."
            ),
        }

    elif expected_step == 6:
        # Step 6: privacy acceptance
        if text.upper().strip() not in ("SI", "SÍ", "S", "YES", "OK", "ACEPTO", "DE ACUERDO"):
            return {
                "ok": False,
                "next_step": 6,
                "message": "Necesito que aceptés las políticas. Respondé *SI* para continuar.",
            }
        profile.privacy_policy_accepted = True
        profile.privacy_policy_accepted_at = datetime.now()
        profile.terms_accepted = True
        profile.terms_accepted_at = datetime.now()
        user.onboarding_step = 7
        await session.flush()
        return {
            "ok": True,
            "next_step": None,  # Done
            "message": (
                "✅ ¡Perfecto! Tus datos quedaron registrados.\n\n"
                "📋 *Resumen de tu registro:*\n"
                f"• Cédula: {profile.id_number}\n"
                f"• Correo: {profile.email}\n"
                f"• Nombre: {profile.full_name}\n"
                f"• Políticas: aceptadas ✅\n\n"
                "Pronto podrás elegir tu plan y pagar para reactivar Lucho. "
                "Te avisamos ni bien esté listo el sistema de pagos. 🚀"
            ),
        }

    return {"ok": False, "next_step": None, "message": "Error: paso no reconocido."}


async def get_post_pago_start_message(session: AsyncSession, user_id: str) -> str:
    """
    Get the starting message for the post-pago flow.
    Called when user first enters post-pago (after trial expires).
    """
    return (
        "⏰ *Tu período de prueba de 7 días terminó.*\n\n"
        "Para continuar usando Lucho, necesito algunos datos. "
        "Son 4 pasos rápidos:\n\n"
        "*Paso 1/4:* ¿Cuál es tu número de cédula o RUC?"
    )
