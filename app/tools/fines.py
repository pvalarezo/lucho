"""Tool: Check vehicle fines by license plate via external API.

This is a PLACEHOLDER that simulates the API call. Replace the API_URL
and response parsing with the actual ANT/SRI/municipal fines endpoint
when available.

Usage:
- Router detects "check_fines" intent → extractor gets plate number
- Tool is executed → API called → result formatted for user
"""

import logging

import httpx

from app.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


class CheckPlateFinesTool(Tool):
    name = "check_plate_fines"
    description = (
        "Consulta si un vehículo tiene multas de tránsito pendientes por su placa. "
        "Usar cuando el usuario pregunta '¿tengo multas?', '¿mi placa tiene multas?', "
        "'¿debo algo de tránsito?', 'consultar multas de PBC-1234'."
    )
    parameters = {
        "plate": {
            "type": "string",
            "description": "Número de placa del vehículo (formato ecuatoriano: ABC-1234 o ABC-123)",
        }
    }

    def __init__(self, api_url: str | None = None, api_key: str | None = None):
        self.api_url = api_url
        self.api_key = api_key

    async def execute(self, params: dict, user_id: str | None = None) -> ToolResult:
        plate = params.get("plate", "").strip().upper()
        if not plate:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="No se proporcionó una placa válida.",
            )

        logger.info("Consultando multas para placa: %s", plate)

        # If API is configured, call it
        if self.api_url:
            return await self._call_api(plate)

        # Otherwise, return placeholder (simulated for development)
        return self._simulate(plate)

    async def _call_api(self, plate: str) -> ToolResult:
        """Call the actual external fines API."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    self.api_url,
                    params={"plate": plate},
                    headers={"Authorization": f"Bearer {self.api_key}"}
                    if self.api_key
                    else {},
                )
                response.raise_for_status()
                data = response.json()

                fines = data.get("fines", data.get("multas", []))
                total = data.get("total", sum(f.get("amount", 0) for f in fines))

                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data={
                        "plate": plate,
                        "total_fines": len(fines),
                        "total_amount": total,
                        "fines": fines,
                    },
                    rendered=self._format_fines(plate, fines, total),
                )

        except httpx.HTTPError as exc:
            logger.error("Fines API error for plate %s: %s", plate, exc)
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Error al consultar multas: {exc}",
            )

    def _simulate(self, plate: str) -> ToolResult:
        """Simulate a response for development/testing."""
        # Simulated: no fines found (happy path for dev)
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "plate": plate,
                "total_fines": 0,
                "total_amount": 0.0,
                "fines": [],
            },
            rendered=self._format_fines(plate, [], 0.0),
        )

    def _format_fines(self, plate: str, fines: list, total: float) -> str:
        """Format fines result as human-readable text."""
        if not fines:
            return f"✅ La placa *{plate}* no tiene multas pendientes."

        lines = [f"🚨 *Multas para {plate}:*"]
        for i, fine in enumerate(fines, 1):
            desc = fine.get("description", fine.get("descripcion", "Multa"))
            amount = fine.get("amount", fine.get("monto", 0))
            date = fine.get("date", fine.get("fecha", ""))
            lines.append(f"  {i}. {desc} — ${amount:.2f}" + (f" ({date})" if date else ""))

        lines.append(f"\n💰 *Total: ${total:.2f}*")
        return "\n".join(lines)


# Create a default instance for registration
check_plate_fines = CheckPlateFinesTool()
