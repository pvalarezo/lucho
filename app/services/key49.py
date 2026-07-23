"""Key49 API client — AURACORE's SRI electronic invoicing platform.

Flow:
  1. create_invoice() → POST /v1/invoices → returns Key49 document id
  2. poll_authorization() → GET /v1/invoices/:id → wait for AUTHORIZED
  3. download_ride() → GET /v1/invoices/:id/ride → PDF for user

Key49 handles: XAdES-BES signing, SRI submission, authorization polling.
Lucho handles: invoice creation, access_key storage, PDF delivery.

Base URL: https://key49.apx5.com/v1
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

KEY49_BASE = "https://key49.apx5.com/v1"

# SRI tax codes for Ecuador (15% IVA as of 2026)
TAX_CODE_IVA = "2"
TAX_RATE_15 = "4"
TAX_RATE_15_VALUE = 15.0

# Payment method codes for SRI
PAYMENT_TRANSFER = "20"
PAYMENT_DEBIT = "16"
PAYMENT_CREDIT = "19"
PAYMENT_CASH = "01"


@dataclass
class Key49Invoice:
    """Result of a Key49 invoice creation."""
    key49_id: str
    establishment: str
    issue_point: str
    sequence_number: str
    access_key: str | None
    status: str
    total_amount: float
    created_at: str | None


async def _api_key() -> str:
    """Get Key49 API key from settings."""
    return settings.KEY49_API_KEY or ""


async def _establishment() -> str:
    return settings.KEY49_ESTABLISHMENT or "001"


async def _issue_point() -> str:
    return settings.KEY49_ISSUE_POINT or "001"


async def create_invoice(
    sequence_number: str,
    recipient_name: str,
    recipient_id: str,
    recipient_id_type: str,
    recipient_email: str,
    recipient_phone: str | None,
    recipient_address: str | None,
    description: str,
    unit_price: float,
    payment_method: str = PAYMENT_TRANSFER,
) -> Key49Invoice | None:
    """
    Send an invoice to Key49 for SRI authorization.

    Args:
        sequence_number: 9-digit sequential (e.g., "000000042")
        recipient_name: Razón social or full name
        recipient_id: RUC (13 digits) or cédula (10 digits)
        recipient_id_type: "04"=RUC, "05"=Cédula, "07"=Consumidor Final
        recipient_email: Email for PDF delivery
        recipient_phone: Phone
        recipient_address: Physical address
        description: Service description (e.g., "Suscripción Lucho Premium - Julio 2026")
        unit_price: Unit price without tax
        payment_method: SRI payment method code

    Returns Key49Invoice or None on failure.
    """
    api_key = await _api_key()
    if not api_key:
        logger.info("Key49 not configured — skipping SRI authorization")
        return None

    # Calculate IVA (15%)
    iva = round(unit_price * 0.15, 2)
    total = round(unit_price + iva, 2)

    establishment = await _establishment()
    issue_point = await _issue_point()

    # Idempotency key: unique per invoice
    idempotency = f"lucho-{sequence_number}-{date.today().isoformat()}"

    payload: dict[str, Any] = {
        "establishment": establishment,
        "issue_point": issue_point,
        "sequence_number": sequence_number,
        "issue_date": date.today().isoformat(),
        "recipient": {
            "id_type": recipient_id_type,
            "id": recipient_id,
            "name": recipient_name,
            "email": recipient_email,
        },
        "items": [
            {
                "main_code": "LUCHO-SUB",
                "description": description,
                "unit_of_measure": "UNIDAD",
                "quantity": 1,
                "unit_price": unit_price,
                "discount": 0.00,
                "taxes": [
                    {
                        "code": TAX_CODE_IVA,
                        "rate_code": TAX_RATE_15,
                        "rate": TAX_RATE_15_VALUE,
                    }
                ],
            }
        ],
        "payments": [
            {
                "payment_method": payment_method,
                "total": total,
                "term": 0,
                "time_unit": "days",
            }
        ],
    }

    if recipient_phone:
        payload["recipient"]["phone"] = recipient_phone
    if recipient_address:
        payload["recipient"]["address"] = recipient_address

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{KEY49_BASE}/invoices",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": idempotency,
                },
            )
            resp.raise_for_status()
            data = resp.json()["data"]

            invoice = Key49Invoice(
                key49_id=data["id"],
                establishment=establishment,
                issue_point=issue_point,
                sequence_number=sequence_number,
                access_key=data.get("access_key"),
                status=data["status"],
                total_amount=total,
                created_at=data.get("created_at"),
            )
            logger.info(
                "Key49 invoice created: id=%s, seq=%s, status=%s",
                invoice.key49_id, sequence_number, invoice.status,
            )
            return invoice

    except httpx.HTTPError as exc:
        logger.error("Key49 invoice creation failed: %s", exc)
        return None


async def poll_authorization(key49_id: str) -> dict[str, Any] | None:
    """
    Poll Key49 for invoice authorization status.

    Returns dict with status, access_key, sri_messages, or None on failure.
    """
    api_key = await _api_key()
    if not api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{KEY49_BASE}/invoices/{key49_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            return resp.json()["data"]
    except httpx.HTTPError as exc:
        logger.error("Key49 poll failed for %s: %s", key49_id, exc)
        return None


async def download_ride(key49_id: str, output_path: str) -> bool:
    """
    Download the PDF (RIDE) for an authorized invoice.

    Returns True on success, False on failure.
    """
    api_key = await _api_key()
    if not api_key:
        return False

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{KEY49_BASE}/invoices/{key49_id}/ride",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(resp.content)
            logger.info("Key49 RIDE downloaded: %s → %s", key49_id, output_path)
            return True
    except Exception as exc:
        logger.error("Key49 RIDE download failed for %s: %s", key49_id, exc)
        return False
