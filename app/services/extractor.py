"""Structured extractor — extracts fields from user messages using Claude Sonnet.

Returns structured data based on the target_table determined by the router.
Each table has its own extraction schema.
"""

import json
import logging
from datetime import date

import httpx
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)


# ---- Per-table extraction schemas ----

class AssetExtraction(BaseModel):
    asset_type: str  # vehicle, credit_card, warranty, subscription, document, insurance, tax, other
    name: str
    attributes: dict = {}
    notes: str | None = None


class EventExtraction(BaseModel):
    title: str
    description: str | None = None
    target_date: str  # ISO date YYYY-MM-DD
    certainty: str = "certain"  # certain | estimated
    recurrence_rule: dict | None = None


class ListItemExtraction(BaseModel):
    list_name: str = "general"
    items: list[str]  # one or more items
    quantity: str | None = None


class NoteExtraction(BaseModel):
    topic_name: str
    content: str


class CorrectionExtraction(BaseModel):
    original_target: str  # what the user is correcting
    corrected_fields: dict  # {field: new_value}


class SharedExpenseExtraction(BaseModel):
    description: str
    amount: float
    currency: str = "USD"
    participants: list[str]  # names or identifiers
    split_type: str = "equal"  # equal | custom
    date: str | None = None  # ISO date


EXTRACTION_SYSTEM_PROMPT = """Eres el extractor de Lucho, un asistente personal ecuatoriano.
Extrae información ESTRUCTURADA del mensaje del usuario según el tipo de dato indicado.

Reglas:
- Fechas: convierte a formato ISO YYYY-MM-DD. Si el usuario dice "mañana", calcula la fecha real. Si dice "15 de julio", asume el año actual.
- Nombres propios: conserva mayúsculas.
- Números: extrae valores numéricos sin símbolos de moneda.
- Placas de Ecuador: formato ABC-1234 o ABC-123.
- Si no estás seguro de un campo, déjalo como null o vacío.
- NO inventes información que el usuario no dio.

Responde ÚNICAMENTE un objeto JSON."""


async def extract_fields(
    text: str,
    target_table: str,
) -> dict:
    """
    Extract structured fields from user text based on target_table.
    Uses Claude Sonnet for high-quality extraction.
    Returns a dict matching the target table's schema.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning empty extraction")
        return {}

    # Build table-specific instructions
    table_prompts = {
        "asset": 'Extrae como: {"asset_type": "vehicle|credit_card|warranty|subscription|document|insurance|tax|other", "name": "nombre descriptivo", "attributes": {campos específicos del tipo}, "notes": "notas adicionales o null}. Para vehicle, attributes incluye: plate, brand, model, year. Para credit_card: bank, last_four_digits. Para warranty: product, store, purchase_date, warranty_months.',
        "event": 'Extrae como: {"title": "título corto", "description": "descripción o null", "target_date": "YYYY-MM-DD", "certainty": "certain|estimated", "recurrence_rule": null o {"freq": "daily|weekly|monthly|yearly", "interval": 1, "days": []}}.',
        "list_item": 'Extrae como: {"list_name": "nombre de la lista", "items": ["ítem1", "ítem2"], "quantity": "cantidad o null"}.',
        "note": 'Extrae como: {"topic_name": "tema corto", "content": "contenido completo"}.',
        "correction": 'Extrae como: {"original_target": "qué se está corrigiendo", "corrected_fields": {"campo": "nuevo valor"}}.',
        "shared_expense": 'Extrae como: {"description": "descripción", "amount": 0.0, "currency": "USD", "participants": ["nombre1", "nombre2"], "split_type": "equal|custom", "date": "YYYY-MM-DD o null"}.',
    }

    prompt = table_prompts.get(target_table, table_prompts["note"])

    logger.info(
        "Extracting fields for target_table=%s from: %s",
        target_table,
        text[:120],
    )

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.ANTHROPIC_SONNET_MODEL,
                    "max_tokens": 500,
                    "messages": [
                        {
                            "role": "user",
                            "content": text,
                        }
                    ],
                    "system": EXTRACTION_SYSTEM_PROMPT + "\n\n" + prompt,
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["content"][0]["text"]
            result = json.loads(content)
            logger.info("Extraction complete: %s", json.dumps(result, ensure_ascii=False)[:200])
            return result

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.error("Extraction failed: %s", exc)
            return {}
