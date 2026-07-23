"""PayPhone API client — Ecuadorian payment gateway.

Flow:
  1. create_payment() → generates a payment link/code
  2. User pays through the PayPhone mobile app
  3. PayPhone sends webhook → handle_webhook() validates and processes
  4. verify_payment() → checks payment status on demand

API docs: https://docs.payphone.app
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PAYPHONE_BASE = settings.PAYPHONE_API_URL.rstrip("/")


@dataclass
class PayPhonePayment:
    """Result of a PayPhone payment creation."""
    payment_id: int
    transaction_id: str
    amount: float
    client_transaction_id: str  # Our reference
    phone_number: str | None
    status: str  # "pending", "approved", "rejected", "expired"
    payment_url: str | None  # Link for user to pay
    created_at: str | None


async def _get_token() -> str:
    """Get an OAuth2 token from PayPhone."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PAYPHONE_BASE}/api/auth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.PAYPHONE_CLIENT_ID,
                "client_secret": settings.PAYPHONE_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]


async def create_payment(
    amount: float,
    description: str,
    reference: str,
    phone_number: str | None = None,
) -> PayPhonePayment | None:
    """
    Create a payment request in PayPhone.

    Args:
        amount: Amount in USD (with cents, e.g. 4.99).
        description: What the user is paying for.
        reference: Our internal transaction ID (for reconciliation).
        phone_number: Optional phone number to pre-fill in PayPhone app.

    Returns PayPhonePayment with payment_url for the user, or None on failure.
    """
    if not settings.PAYPHONE_CLIENT_ID:
        logger.warning("PayPhone not configured — skipping payment creation")
        return None

    try:
        token = await _get_token()
    except httpx.HTTPError as exc:
        logger.error("PayPhone auth failed: %s", exc)
        return None

    amount_cents = int(round(amount * 100))  # PayPhone expects cents

    payload: dict[str, Any] = {
        "amount": amount_cents,
        "amountWithoutTax": amount_cents,
        "amountWithTax": 0,  # Tax handled separately for SRI
        "description": description[:80],
        "clientTransactionId": reference,
        "storeId": settings.PAYPHONE_STORE_ID,
        "phoneNumber": phone_number or "",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{PAYPHONE_BASE}/api/button",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            payment = PayPhonePayment(
                payment_id=data.get("paymentId", 0),
                transaction_id=str(data.get("transactionId", "")),
                amount=amount,
                client_transaction_id=reference,
                phone_number=data.get("phoneNumber"),
                status=data.get("status", "pending"),
                payment_url=data.get("payUrl"),
                created_at=data.get("date"),
            )
            logger.info(
                "PayPhone payment created: id=%s, amount=%.2f, ref=%s, url=%s",
                payment.payment_id, payment.amount, reference, payment.payment_url,
            )
            return payment

    except httpx.HTTPError as exc:
        logger.error("PayPhone payment creation failed: %s", exc)
        return None


async def verify_payment(transaction_id: str) -> dict[str, Any] | None:
    """
    Check the status of a PayPhone payment by transaction ID.

    Returns dict with status and details, or None on failure.
    """
    if not settings.PAYPHONE_CLIENT_ID:
        return None

    try:
        token = await _get_token()
    except httpx.HTTPError:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{PAYPHONE_BASE}/api/button/{transaction_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.error("PayPhone verify failed for %s: %s", transaction_id, exc)
        return None


def validate_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Validate the HMAC-SHA256 signature from PayPhone webhook.

    PayPhone signs the raw JSON body with the webhook secret.
    """
    if not settings.PAYPHONE_WEBHOOK_SECRET:
        logger.warning("PayPhone webhook secret not configured — accepting all")
        return True

    expected = hmac.new(
        settings.PAYPHONE_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def process_webhook(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Process a PayPhone webhook payment confirmation.

    Returns processed payment data, or None if invalid.
    """
    transaction_id = payload.get("transactionId") or payload.get("clientTransactionId")
    status = payload.get("status", "").lower()

    if not transaction_id:
        logger.warning("PayPhone webhook missing transactionId")
        return None

    logger.info(
        "PayPhone webhook received: tx=%s, status=%s",
        transaction_id, status,
    )

    return {
        "transaction_id": str(transaction_id),
        "status": status,
        "amount": float(payload.get("amount", 0)) / 100,  # Convert from cents
        "payment_id": payload.get("paymentId"),
        "authorization_code": payload.get("authorizationCode"),
        "phone_number": payload.get("phoneNumber"),
        "raw": payload,
    }
