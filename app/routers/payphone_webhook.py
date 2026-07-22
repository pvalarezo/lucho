"""PayPhone webhook endpoint — receives payment confirmations from PayPhone.

POST /webhooks/payphone
  - Validates HMAC signature
  - Processes payment confirmation
  - Activates subscription
  - Sends confirmation message to user
"""

import json
import logging
import uuid as _uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.subscription import (
    Subscription,
    SubscriptionStatus,
    Payment,
    PaymentStatus,
    SubscriptionInvoice,
)
from app.models.user import User
from app.services import payphone as payphone_svc
from app.services.notifications import send_notification, resolve_user_contact

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/payphone")
async def payphone_webhook(request: Request):
    """
    Handle PayPhone payment confirmation webhook.

    PayPhone sends a POST with JSON body and X-PayPhone-Signature header.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-PayPhone-Signature", "")

    if not payphone_svc.validate_webhook_signature(raw_body, signature):
        logger.warning("PayPhone webhook: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("PayPhone webhook: invalid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    payment_data = await payphone_svc.process_webhook(payload)
    if not payment_data:
        raise HTTPException(status_code=400, detail="Missing transaction ID")

    async with async_session() as session:
        await _activate_subscription(session, payment_data)
        await session.commit()

    return {"status": "ok"}


async def _activate_subscription(session, payment_data: dict):
    """Find payment, mark completed, activate subscription, notify user."""
    ref = payment_data["transaction_id"]
    status = payment_data["status"]

    result = await session.execute(
        select(Payment).where(Payment.gateway_payment_id == ref)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        logger.warning("PayPhone webhook: no payment found for ref %s", ref)
        return

    if status == "approved":
        payment.status = PaymentStatus.completed
        payment.completed_at = datetime.now(timezone.utc)
        payment.gateway_status = "approved"

        # Activate subscription
        sub_result = await session.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan_ref))
            .where(Subscription.id == payment.subscription_id)
        )
        subscription = sub_result.scalar_one_or_none()

        if subscription:
            now = datetime.now(timezone.utc)
            subscription.status = SubscriptionStatus.active
            subscription.current_period_start = now
            if subscription.renewal_type and hasattr(subscription.renewal_type, 'value') and subscription.renewal_type.value == "annual":
                subscription.current_period_end = now + timedelta(days=365)
            else:
                subscription.current_period_end = now + timedelta(days=30)
            subscription.trial_ends_at = None

            # Generate invoice
            invoice = SubscriptionInvoice(
                payment_id=payment.id,
                invoice_number=_generate_invoice_number(payment.id),
                amount=payment.amount,
                issued_at=now,
            )
            session.add(invoice)

            # Notify user
            await _notify_activation(session, subscription)

            plan_name = subscription.plan_ref.name if subscription.plan_ref else "?"
            logger.info(
                "Subscription activated: user=%s, plan=%s",
                subscription.user_id, plan_name,
            )
    else:
        payment.status = PaymentStatus.failed
        payment.gateway_status = status
        logger.info("PayPhone payment %s: %s", ref, status)


def _generate_invoice_number(payment_id: _uuid.UUID) -> str:
    short_id = str(payment_id)[:8].upper()
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"LUCHO-{date_str}-{short_id}"


async def _notify_activation(session, subscription):
    """Send activation message to user."""
    user_result = await session.execute(
        select(User).where(User.id == subscription.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return

    contact_id, channel = await resolve_user_contact(user)
    if not contact_id:
        return

    plan_name = subscription.plan_ref.name if subscription.plan_ref else "activo"
    until = subscription.current_period_end.strftime("%d/%m/%Y") if subscription.current_period_end else ""

    msg = (
        f"✅ *¡Suscripción activada!*\n\n"
        f"Plan: {plan_name}\n"
        f"Vence: {until}\n\n"
        f"Gracias por confiar en Lucho. ¡A organizar se ha dicho! 🇪🇨"
    )

    await send_notification(
        user_id=str(subscription.user_id),
        contact_id=contact_id,
        message=msg,
        channel=channel,
    )
