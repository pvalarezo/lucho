"""LLM provider interface — abstract base for all LLM backends."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base for LLM providers (Anthropic, DeepSeek, etc.)."""

    def __init__(self, api_key: str, router_model: str, extractor_model: str):
        self.api_key = api_key
        self.router_model = router_model
        self.extractor_model = extractor_model

    @abstractmethod
    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        max_tokens: int = 500,
    ) -> str:
        """Send a chat completion and return the text response."""

    async def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        max_tokens: int = 500,
    ) -> dict:
        """Send a chat completion and parse the response as JSON."""
        import json
        import logging

        logger = logging.getLogger(__name__)
        text = await self.chat(system_prompt, user_message, model, max_tokens)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON: %s", text[:200])
            return {}

    async def route(self, user_message: str) -> dict:
        """Route intent using the economical router model."""
        return await self.chat_json(
            self._get_router_prompt(), user_message, self.router_model, 150
        )

    async def extract(self, user_message: str, target_table: str) -> dict:
        """Extract structured fields using the extractor model."""
        prompt = self._get_extractor_prompt(target_table)
        return await self.chat_json(prompt, user_message, self.extractor_model, 500)

    # ---- Prompts (shared across providers) ----
    # Subclasses can override if needed for provider-specific tuning.

    def _get_router_prompt(self) -> str:
        return """Eres el router de intención de Lucho, un asistente personal ecuatoriano.

Tu única tarea es clasificar el mensaje del usuario en UNA de estas categorías, siguiendo este árbol de decisión en orden:

1. **asset**: El mensaje describe un bien/entidad que el usuario POSEE y que genera eventos futuros (carro con placa, tarjeta de crédito, garantía de electrodoméstico, suscripción, documento como cédula/pasaporte, seguro). NO importa si menciona una fecha — si hay una entidad que se posee, es asset.

2. **event**: El mensaje describe algo que VA A PASAR en una fecha específica, sin describir un bien que se posee.

3. **list_item**: El mensaje describe un ítem de lista con estado pendiente/hecho (compras, tareas, pendientes).

4. **note**: Contenido libre que no encaja en las anteriores — ideas, reflexiones, información que el usuario quiere guardar.

5. **search**: El usuario está PREGUNTANDO por información que ya guardó.

6. **correction**: El usuario está CORRIGIENDO lo que Lucho acaba de entender mal.

7. **shared_expense**: El usuario está registrando un gasto compartido entre varias personas.

Responde ÚNICAMENTE un objeto JSON con:
{
  "target_table": "asset|event|list_item|note|search|correction|shared_expense",
  "reasoning": "una frase corta explicando por qué"
}"""

    def _get_extractor_prompt(self, target_table: str) -> str:
        from datetime import date
        today = date.today()
        weekday = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"][today.weekday()]

        base = f"""Eres el extractor de Lucho, un asistente personal ecuatoriano.
Extrae información ESTRUCTURADA del mensaje del usuario según el tipo de dato indicado.

FECHA ACTUAL: {today.isoformat()} ({weekday}, año {today.year})

Reglas:
- Fechas: convierte a formato ISO YYYY-MM-DD. "mañana" = {today.day+1}, "próximo lunes" calcula desde hoy ({weekday}). SIEMPRE usa el año {today.year} a menos que el usuario diga otro explícitamente.
- Placas de Ecuador: formato ABC-1234 o ABC-123.
- Si no estás seguro de un campo, déjalo como null o vacío.
- NO inventes información que el usuario no dio.

Responde ÚNICAMENTE un objeto JSON."""

        table_prompts = {
            "asset": 'Extrae: {"asset_type": "vehicle|credit_card|warranty|subscription|document|insurance|tax|other", "name": "nombre descriptivo", "attributes": {campos específicos}, "notes": "notas o null}. Vehicle: plate, brand, model, year. Credit_card: bank, last_four_digits. Warranty: product, store, purchase_date, warranty_months.',
            "event": 'Extrae: {"title": "título corto", "description": "descripción o null", "target_date": "YYYY-MM-DD", "certainty": "certain|estimated", "recurrence_rule": null o {"freq": "daily|weekly|monthly|yearly", "interval": 1, "days": []}}.',
            "list_item": 'Extrae: {"list_name": "nombre de la lista", "items": ["ítem1", "ítem2"], "quantity": "cantidad o null"}.',
            "note": 'Extrae: {"topic_name": "tema corto", "content": "contenido completo"}.',
            "correction": 'Extrae: {"original_target": "qué se está corrigiendo", "corrected_fields": {"campo": "nuevo valor"}}.',
            "shared_expense": 'Extrae: {"description": "descripción", "amount": 0.0, "currency": "USD", "participants": ["nombre1"], "split_type": "equal|custom", "date": "YYYY-MM-DD o null"}.',
            "search": 'Extrae: {"search_type": "vehicle|list|deadline|note|pending|general", "entity_name": "nombre de lo que busca (ej: carro, compras, SOAT)", "specific_field": "campo específico o null"}. Usa search_type=vehicle si pregunta por carro, vehículo, placa, SOAT, matriculación. Usa list/pending si pregunta por compras, pendientes, tareas. Usa deadline si pregunta por fechas, vencimientos. Usa note si pregunta por ideas, notas, temas.',
        }

        return base + "\n\n" + table_prompts.get(target_table, table_prompts["note"])
