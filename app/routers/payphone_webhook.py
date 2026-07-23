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
    InvoiceStatus,
)
from app.models.billing_info import BillingInfo
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

            # Generate invoice with billing info
            await _create_invoice(session, payment, subscription)

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


async def _create_invoice(session, payment, subscription) -> SubscriptionInvoice:
    """Create an SRI-compliant invoice with billing info from the user's default profile."""
    now = datetime.now(timezone.utc)

    # Find default billing info
    billing_result = await session.execute(
        select(BillingInfo).where(
            BillingInfo.user_id == payment.user_id,
            BillingInfo.is_default is True,
            BillingInfo.is_active is True,
        )
    )
    billing = billing_result.scalar_one_or_none()

    # Fallback: use UserProfile data
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
    await session.flush()
    logger.info("Invoice created: %s for user=%s, amount=%.2f",
                invoice.invoice_number, payment.user_id, payment.amount)

    # Submit to Key49 for SRI authorization (non-blocking — scheduler polls)
    await _submit_to_key49(session, invoice)

    return invoice


async def _submit_to_key49(session, invoice: SubscriptionInvoice):
    """Submit invoice to Key49 for SRI authorization (fire and forget)."""
    from app.services import key49 as key49_svc

    # Map id_type to SRI code
    id_type_map = {"cedula": "05", "ruc": "04", "pasaporte": "06", "consumidor_final": "07"}
    sri_id_type = id_type_map.get(invoice.billing_id_type, "05")

    # Calculate unit price (amount is with IVA, need base)
    base_amount = round(float(invoice.amount) / 1.15, 2)

    result = await key49_svc.create_invoice(
        sequence_number=invoice.invoice_number.split("-")[-1] if "-" in (invoice.invoice_number or "") else "000000001",
        recipient_name=invoice.billing_name or "Consumidor Final",
        recipient_id=invoice.billing_id_number or "9999999999999",
        recipient_id_type=sri_id_type,
        recipient_email=invoice.billing_email or "",
        recipient_phone=invoice.billing_phone,
        recipient_address=invoice.billing_address,
        description=f"Suscripción Lucho — {invoice.invoice_number}",
        unit_price=base_amount,
        payment_method="20",  # Transferencia
    )

    if result:
        invoice.key49_id = result.key49_id
        if result.access_key:
            invoice.sri_access_key = result.access_key
        await session.flush()
        logger.info("Key49 submission: invoice=%s, key49_id=%s, status=%s",
                   invoice.invoice_number, result.key49_id, result.status)


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
