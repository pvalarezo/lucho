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

    # Use DeepSeek (OpenAI-compatible vision)
    if settings.LLM_PROVIDER == "deepseek" and settings.DEEPSEEK_API_KEY:
        return await _deepseek_vision(image_b64)

    # Use Anthropic Claude Vision
    if settings.LLM_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        return await _anthropic_vision(image_b64)

    return None


async def _deepseek_vision(image_b64: str) -> dict | None:
    """Analyze image with DeepSeek Vision."""
    import json

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
                    "max_tokens": 200,
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
                                    "text": VISION_PROMPT,
                                },
                            ],
                        }
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            result = json.loads(text)
            logger.info(
                "Vision: %s (confidence: %s, action: %s)",
                result.get("document_type", "?"),
                result.get("confidence", "?"),
                result.get("suggested_action", "?"),
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
