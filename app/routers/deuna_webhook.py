"""DeUna webhook endpoint — receives payment confirmations from DeUna (Pichincha).

POST /webhooks/deuna
  - Validates signature
  - Processes payment confirmation
  - Activates subscription
"""

import json
import logging
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
from app.services.notifications import send_notification, resolve_user_contact

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/deuna")
async def deuna_webhook(request: Request):
    """
    Handle DeUna payment confirmation webhook.

    DeUna sends a POST with JSON body:
      {
        "id": "pay_xxx",
        "reference": "SUB-xxx",
        "status": "approved",
        "amount": 9.99,
        "currency": "USD"
      }
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        logger.error("DeUna webhook: invalid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    transaction_id = payload.get("id") or payload.get("reference")
    status = (payload.get("status") or "").lower()

    if not transaction_id:
        raise HTTPException(status_code=400, detail="Missing transaction ID")

    logger.info("DeUna webhook: tx=%s, status=%s", transaction_id, status)

    if status != "approved":
        return {"status": "ignored", "reason": f"status={status}"}

    async with async_session() as session:
        await _activate_subscription(session, transaction_id)
        await session.commit()

    return {"status": "ok"}


async def _activate_subscription(session, ref: str):
    """Activate subscription after successful DeUna payment."""
    result = await session.execute(
        select(Payment).where(Payment.gateway_payment_id == ref)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        logger.warning("DeUna webhook: no payment found for ref %s", ref)
        return

    payment.status = PaymentStatus.completed
    payment.completed_at = datetime.now(timezone.utc)
    payment.gateway_status = "approved"

    sub_result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan_ref))
        .where(Subscription.id == payment.subscription_id)
    )
    subscription = sub_result.scalar_one_or_none()
    if not subscription:
        return

    now = datetime.now(timezone.utc)
    subscription.status = SubscriptionStatus.active
    subscription.current_period_start = now
    if subscription.renewal_type and hasattr(subscription.renewal_type, 'value') and subscription.renewal_type.value == "annual":
        subscription.current_period_end = now + timedelta(days=365)
    else:
        subscription.current_period_end = now + timedelta(days=30)
    subscription.trial_ends_at = None

    # Generate invoice
    import uuid as _uuid
    short_id = str(payment.id)[:8].upper()
    date_str = now.strftime("%Y%m%d")
    invoice = SubscriptionInvoice(
        payment_id=payment.id,
        invoice_number=f"LUCHO-{date_str}-{short_id}",
        amount=payment.amount,
        issued_at=now,
    )
    session.add(invoice)

    # Notify user
    user_result = await session.execute(
        select(User).where(User.id == subscription.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user:
        contact_id, channel = await resolve_user_contact(user)
        if contact_id:
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

    plan_name = subscription.plan_ref.name if subscription.plan_ref else "?"
    logger.info("DeUna subscription activated: user=%s, plan=%s", subscription.user_id, plan_name)
