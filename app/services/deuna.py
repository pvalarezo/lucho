"""DeUna API client — Banco Pichincha payment gateway (Ecuador).

Flow:
  1. create_payment() → generates a payment URL
  2. User opens link → pays with any Ecuadorian bank account
  3. DeUna sends webhook → confirmation

DeUna is Ecuador's interbank payment button — works with all major banks
through the Pichincha network.

API docs: https://deuna.com / https://api.deuna.com
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DEUNA_BASE = "https://api.deuna.com"  # Production endpoint


@dataclass
class DeUnaPayment:
    payment_id: str
    amount: float
    status: str
    payment_url: str | None
    qr_code_url: str | None
    reference: str


async def create_payment(
    amount: float,
    description: str,
    reference: str,
) -> DeUnaPayment | None:
    """
    Create a payment link via DeUna.

    Returns DeUnaPayment with payment_url, or None if not configured.
    """
    deuna_api_key = getattr(settings, 'DEUNA_API_KEY', '')
    deuna_merchant_id = getattr(settings, 'DEUNA_MERCHANT_ID', '')

    if not deuna_api_key or not deuna_merchant_id:
        logger.info("DeUna not configured — skipping")
        return None

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{DEUNA_BASE}/v1/checkout",
                json={
                    "merchantId": deuna_merchant_id,
                    "amount": amount,
                    "currency": "USD",
                    "description": description[:100],
                    "reference": reference,
                    "returnUrl": "https://lucho-dev.apx5.com",
                },
                headers={
                    "Authorization": f"Bearer {deuna_api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            payment = DeUnaPayment(
                payment_id=data.get("id", ""),
                amount=amount,
                status=data.get("status", "pending"),
                payment_url=data.get("checkoutUrl") or data.get("paymentUrl"),
                qr_code_url=data.get("qrCode") or data.get("qrUrl") or data.get("checkoutUrl"),
                reference=reference,
            )
            logger.info("DeUna payment created: %s, url=%s", payment.payment_id, payment.payment_url)
            return payment

    except httpx.HTTPError as exc:
        logger.error("DeUna payment creation failed: %s", exc)
        return None
    except Exception as exc:
        logger.exception("DeUna unexpected error: %s", exc)
        return None
