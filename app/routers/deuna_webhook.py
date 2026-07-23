"""DeUna webhook endpoint — receives payment confirmations from DeUna (Pichincha).

POST /webhooks/deuna
  - Validates HMAC signature (X-DeUna-Signature header)
  - Verifies amount, currency, and reference match the pending payment
  - Idempotent: ignores already-completed payments
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
    InvoiceStatus,
)
from app.models.user import User
from app.models.billing_info import BillingInfo
from app.services import deuna as deuna_svc
from app.services.notifications import send_notification, resolve_user_contact

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/deuna")
async def deuna_webhook(request: Request):
    """
    Handle DeUna payment confirmation webhook.

    Authenticated via HMAC-SHA256 signature in X-DeUna-Signature header.
    DeUna sends a POST with JSON body:
      {
        "id": "pay_xxx",
        "reference": "SUB-xxx",
        "status": "approved",
        "amount": 9.99,
        "currency": "USD"
      }
    """
    raw_body = await request.body()
    signature = request.headers.get("X-DeUna-Signature", "")

    # ---- Signature validation ----
    if not deuna_svc.validate_webhook_signature(raw_body, signature):
        logger.warning("DeUna webhook: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("DeUna webhook: invalid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    payment_data = deuna_svc.process_webhook(payload)
    if not payment_data:
        raise HTTPException(status_code=400, detail="Missing transaction ID")

    transaction_id = payment_data["transaction_id"]
    status = payment_data["status"]

    if status != "approved":
        return {"status": "ignored", "reason": f"status={status}"}

    async with async_session() as session:
        await _activate_subscription(session, payment_data)
        await session.commit()

    return {"status": "ok"}


async def _activate_subscription(session, payment_data: dict):
    """Find payment, validate amount/currency, mark completed, activate subscription, notify user."""
    ref = payment_data["transaction_id"]
    webhook_amount = payment_data["amount"]
    webhook_currency = payment_data["currency"]

    result = await session.execute(
        select(Payment).where(Payment.gateway_payment_id == ref)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        logger.warning("DeUna webhook: no payment found for ref %s", ref)
        return

    # ---- Idempotency: skip already-completed payments ----
    if payment.status == PaymentStatus.completed:
        logger.info("DeUna webhook: payment %s already completed — idempotent skip", ref)
        return

    # ---- Validate currency ----
    if webhook_currency != "USD":
        logger.warning(
            "DeUna webhook: unexpected currency %s for tx %s", webhook_currency, ref
        )
        return

    # ---- Validate amount (within 1 cent tolerance) ----
    stored_amount = float(payment.amount)
    if abs(webhook_amount - stored_amount) > 0.01:
        logger.warning(
            "DeUna webhook: amount mismatch for tx %s — webhook=%.2f, stored=%.2f",
            ref, webhook_amount, stored_amount,
        )
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

    # Generate invoice with billing info
    await _create_invoice(session, payment, subscription)

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


async def _create_invoice(session, payment, subscription) -> SubscriptionInvoice:
    """Create an SRI-compliant invoice with billing info from user's default profile."""
    now = datetime.now(timezone.utc)

    billing_result = await session.execute(
        select(BillingInfo).where(
            BillingInfo.user_id == payment.user_id,
            BillingInfo.is_default == True,
            BillingInfo.is_active == True,
        )
    )
    billing = billing_result.scalar_one_or_none()

    if not billing:
        from app.models.user_profile import UserProfile
        profile_result = await session.execute(
            select(UserProfile).where(UserProfile.user_id == payment.user_id)
        )
        profile = profile_result.scalar_one_or_none()
        invoice = SubscriptionInvoice(
            payment_id=payment.id,
            invoice_number=_generate_invoice_number(payment.id),
            billing_name=profile.full_name if profile else None,
            billing_id_number=profile.id_number if profile else None,
            billing_id_type="cedula",
            billing_email=profile.email if profile else None,
            billing_phone=profile.phone if profile else None,
            billing_address=profile.address if profile else None,
            amount=payment.amount,
            status=InvoiceStatus.issued,
            issued_at=now,
        )
    else:
        invoice = SubscriptionInvoice(
            payment_id=payment.id,
            invoice_number=_generate_invoice_number(payment.id),
            billing_name=billing.full_name,
            billing_id_number=billing.id_number,
            billing_id_type=billing.id_type,
            billing_email=billing.email,
            billing_phone=billing.phone,
            billing_address=billing.address,
            amount=payment.amount,
            status=InvoiceStatus.issued,
            issued_at=now,
        )

    session.add(invoice)
    return invoice


def _generate_invoice_number(payment_id) -> str:
    """Generate a sequential invoice number from payment UUID."""
    raw = str(payment_id).replace("-", "")
    return f"001-001-{raw[:9]}"
