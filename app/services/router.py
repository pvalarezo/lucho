"""Intent router — classifies user messages using Claude Haiku (economical model).

Returns structured output with a closed enum of target tables.
The decision tree follows the spec (section 9.4):
1. Entity with attributes that generate future events → asset
2. Has its own date → event
3. Has a status (pending/done) → list_item
4. None of the above → note

Additional orthogonal paths:
- Mentions a project → handled separately (project_task)
- Asks a question → search
- Corrects previous extraction → correction
- Shared expense → shared_expense
"""

import json
import logging
from enum import Enum

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TargetTable(str, Enum):
    asset = "asset"
    event = "event"
    list_item = "list_item"
    note = "note"
    search = "search"
    correction = "correction"
    shared_expense = "shared_expense"


ROUTER_SYSTEM_PROMPT = """Eres el router de intención de Lucho, un asistente personal ecuatoriano.

Tu única tarea es clasificar el mensaje del usuario en UNA de estas categorías, siguiendo este árbol de decisión en orden:

1. **asset**: El mensaje describe un bien/entidad que el usuario POSEE y que genera eventos futuros (carro con placa, tarjeta de crédito, garantía de electrodoméstico, suscripción, documento como cédula/pasaporte, seguro). NO importa si menciona una fecha — si hay una entidad que se posee, es asset. Ej: "mi carro PBC-1234", "tarjeta Visa del Produbanco", "garantía de la lavadora LG".

2. **event**: El mensaje describe algo que VA A PASAR en una fecha específica, sin describir un bien que se posee. Ej: "cita médica el 15 de julio", "reunión con el contador mañana", "recordarme llamar a mamá el viernes".

3. **list_item**: El mensaje describe un ítem de lista con estado pendiente/hecho (compras, tareas, pendientes). Ej: "comprar leche y pan", "tengo que lavar el carro", "llamar al banco y pagar la luz".

4. **note**: Contenido libre que no encaja en las anteriores — ideas, reflexiones, información que el usuario quiere guardar. Ej: "idea de negocio: vender empanadas online", "receta de la abuela".

5. **search**: El usuario está PREGUNTANDO por información que ya guardó. Ej: "¿dónde guardé la factura del refri?", "¿cuándo vence mi SOAT?", "¿cuánto he gastado en supermercado este mes?".

6. **correction**: El usuario está CORRIGIENDO lo que Lucho acaba de entender mal. Ej: "no, la cita es el 20 no el 15", "el carro es PBC-1234 no PBC-1235".

7. **shared_expense**: El usuario está registrando un gasto compartido entre varias personas. Ej: "pagué la cena, éramos 4", "el arriendo de julio, dividir entre 3".

Responde ÚNICAMENTE un objeto JSON con estos campos:
{
  "target_table": "asset|event|list_item|note|search|correction|shared_expense",
  "reasoning": "una frase corta explicando por qué elegiste esa categoría"
}"""


async def route_intent(text: str) -> dict:
    """
    Classify user message into a target table using Claude Haiku.
    Returns {"target_table": str, "reasoning": str}.
    Falls back to "note" if the LLM call fails.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — defaulting to 'note'")
        return {"target_table": "note", "reasoning": "api_key_missing"}

    logger.info("Routing intent: %s", text[:120])

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.ANTHROPIC_HAIKU_MODEL,
                    "max_tokens": 150,
                    "messages": [
                        {
                            "role": "user",
                            "content": text,
                        }
                    ],
                    "system": ROUTER_SYSTEM_PROMPT,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Extract text from Claude's response
            content = data["content"][0]["text"]
            result = json.loads(content)
            logger.info(
                "Intent routed → %s (reasoning: %s)",
                result["target_table"],
                result.get("reasoning", ""),
            )
            return result

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.error("Intent routing failed: %s", exc)
            return {"target_table": "note", "reasoning": f"router_error: {exc}"}
