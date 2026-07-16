"""Vision service — analyze images using DeepSeek Vision (or configured LLM).

Used when user sends a photo without caption. Lucho analyzes the image
and asks: 'Parece una cédula. ¿La guardo en tus documentos?'
"""

import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

VISION_PROMPT = """Analizá esta imagen y respondé ÚNICAMENTE un JSON con esta estructura:

{
  "document_type": "cedula|factura|soat|licencia|pasaporte|garantia|recibo|contrato|otro",
  "description": "descripción corta de lo que ves (máximo 50 caracteres)",
  "suggested_action": "guardar|preguntar|ignorar",
  "confidence": "alta|media|baja"
}

Reglas:
- Si es un DOCUMENTO PERSONAL (cédula, pasaporte, licencia) → suggested_action="guardar"
- Si es una FACTURA o RECIBO → suggested_action="guardar" 
- Si es un DOCUMENTO DE VEHÍCULO (SOAT, matrícula) → suggested_action="guardar"
- Si es una GARANTÍA → suggested_action="guardar"
- Si es una captura de pantalla de chat/redes sociales → suggested_action="ignorar"
- Si es un meme o imagen no relacionada → suggested_action="ignorar"
- Si no estás seguro → suggested_action="preguntar"
- NO inventes información. Solo describí lo que ves."""

OCR_EXTRACTION_PROMPT = """Analizá esta imagen de documento ecuatoriano y extraé TODA la información relevante.
Respondé ÚNICAMENTE un JSON.

## Si es un SOAT o documento de vehículo:
{
  "document_type": "soat",
  "plate": "ABC1234",
  "insurer": "Seguros Equinoccial",
  "policy_number": "123456",
  "valid_from": "2026-01-15",
  "valid_until": "2027-01-15",
  "vehicle_brand": "Toyota",
  "vehicle_model": "Corolla",
  "vehicle_year": 2020,
  "owner_name": "Juan Pérez"
}

## Si es una factura o recibo:
{
  "document_type": "factura",
  "business_name": "Supermaxi",
  "ruc": "1790012345001",
  "invoice_number": "001-002-000123456",
  "date": "2026-07-12",
  "total": 47.30,
  "subtotal": 40.08,
  "iva": 7.22,
  "items": ["leche entera 1L", "pan integral", "huevos x12"]
}

## Si es una cédula de identidad:
{
  "document_type": "cedula",
  "full_name": "Juan Carlos Pérez Rodríguez",
  "id_number": "1712345678",
  "birth_date": "1990-05-15",
  "issue_date": "2020-01-10",
  "expiry_date": "2030-01-10"
}

## Si es una licencia de conducir:
{
  "document_type": "licencia",
  "full_name": "Juan Carlos Pérez Rodríguez",
  "id_number": "1712345678",
  "license_number": "1234567890",
  "category": "B",
  "issue_date": "2021-06-20",
  "expiry_date": "2026-06-20"
}

## Si es una garantía:
{
  "document_type": "garantia",
  "product": "Lavadora LG WT19SB",
  "store": "Almacenes Japón",
  "purchase_date": "2026-01-10",
  "warranty_months": 24,
  "expiry_date": "2028-01-10",
  "serial_number": "LG2026WT19SB123"
}

## Si es una matrícula vehicular:
{
  "document_type": "matricula",
  "plate": "ABC1234",
  "owner_name": "Juan Pérez",
  "vehicle_brand": "Toyota",
  "vehicle_model": "Corolla",
  "vehicle_year": 2020,
  "registration_date": "2026-04-15",
  "expiry_date": "2027-04-15",
  "canton": "Quito"
}

Reglas:
- Convertí todas las fechas a formato ISO YYYY-MM-DD
- Si un campo no está visible, ponelo como null
- El número de placa va sin guión (ABC1234)
- El RUC son 13 dígitos
- El número de cédula son 10 dígitos
- NO inventes. Solo extraé lo que ves claramente."""


async def extract_document_data(image_bytes: bytes) -> dict | None:
    """
    Extract structured data from a document image using OCR.
    Uses DeepSeek Vision as primary (we have the key).
    Falls back to Anthropic Claude Vision → OpenAI Vision.
    """
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Primary: DeepSeek Vision (deepseek-chat, OpenAI-compatible, key configured)
    if settings.DEEPSEEK_API_KEY:
        result = await _deepseek_ocr(image_b64)
        if result:
            return result

    # Fallback 1: Anthropic Claude Vision
    if settings.ANTHROPIC_API_KEY:
        return await _anthropic_ocr(image_b64)

    # Fallback 2: OpenAI Vision
    if settings.OPENAI_API_KEY:
        return await _openai_ocr(image_b64)

    logger.warning("No vision-capable API key configured for OCR")
    return None


async def _deepseek_ocr(image_b64: str) -> dict | None:
    """Extract document data using DeepSeek Vision (deepseek-chat).
    Uses OCR_EXTRACTION_PROMPT for structured extraction."""
    return await _deepseek_vision(image_b64, prompt=OCR_EXTRACTION_PROMPT)


async def _anthropic_ocr(image_b64: str) -> dict | None:
    """Extract document data using Anthropic Claude Vision."""
    import json

    async with httpx.AsyncClient(timeout=45) as client:
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
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": image_b64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": OCR_EXTRACTION_PROMPT,
                                },
                            ],
                        }
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["content"][0]["text"]
            # Extract JSON from markdown code blocks if present
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            result = json.loads(text)
            logger.info("Anthropic OCR: %s", result.get("document_type", "?"))
            return result
        except Exception as exc:
            logger.error("Anthropic OCR failed: %s", exc)
            return None


async def _openai_ocr(image_b64: str) -> dict | None:
    """Extract document data using OpenAI Vision."""
    import json

    async with httpx.AsyncClient(timeout=45) as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 500,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}",
                                        "detail": "high",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": OCR_EXTRACTION_PROMPT,
                                },
                            ],
                        }
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            result = json.loads(text)
            logger.info("OpenAI OCR: %s", result.get("document_type", "?"))
            return result
        except Exception as exc:
            logger.error("OpenAI OCR failed: %s", exc)
            return None


async def analyze_image(image_bytes: bytes) -> dict | None:
    """
    Analyze an image using the LLM's vision capabilities.
    Returns a dict with document_type, description, suggested_action, confidence.
    Returns None on failure.
    """
    if not settings.DEEPSEEK_API_KEY and not settings.ANTHROPIC_API_KEY:
        logger.warning("No vision-capable API key configured")
        return None

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    if settings.LLM_PROVIDER == "deepseek" and settings.DEEPSEEK_API_KEY:
        return await _deepseek_vision(image_b64)

    if settings.LLM_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        return await _anthropic_vision(image_b64)

    return None


async def _deepseek_vision(image_b64: str, prompt: str | None = None) -> dict | None:
    """Analyze image with DeepSeek Vision. Uses OCR_EXTRACTION_PROMPT if prompt provided."""
    import json

    text_prompt = prompt or VISION_PROMPT

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "max_tokens": 500,
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}"
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": text_prompt,
                                },
                            ],
                        }
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            # Extract JSON from markdown code blocks if present
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            result = json.loads(text)
            logger.info(
                "Vision: %s (confidence: %s, action: %s)",
                result.get("document_type", "?"),
                result.get("confidence", "?"),
                result.get("suggested_action", result.get("plate", "?")),
            )
            return result

        except Exception as exc:
            logger.error("DeepSeek Vision failed: %s", exc)
            return None


async def _anthropic_vision(image_b64: str) -> dict | None:
    """Analyze image with Anthropic Claude Vision."""
    import json

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
                    "max_tokens": 200,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": image_b64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": VISION_PROMPT,
                                },
                            ],
                        }
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["content"][0]["text"]
            result = json.loads(text)
            logger.info("Vision: %s", result.get("document_type", "?"))
            return result

        except Exception as exc:
            logger.error("Anthropic Vision failed: %s", exc)
            return None
