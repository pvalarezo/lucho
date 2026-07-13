"""
Lucho Agent Tools — what Lucho can DO.

Each tool has two parts:
1. Schema (OpenAI/DeepSeek function-calling format) — what the LLM sees
2. Handler (async Python function) — what actually executes (DETERMINISTIC)

The LLM decides WHICH tool to call and WITH WHAT parameters.
The handler does the actual database work. The LLM NEVER generates SQL.

Multi-tenant: every handler takes user_id and filters by it.
All handlers return structured dicts that the LLM uses to craft the response.
"""

import logging
from typing import Any

from app.services.persistence import (
    persist_asset,
    persist_event,
    persist_list_items,
    persist_note,
    persist_shared_expense,
)
from app.services.search import (
    semantic_search,
    upcoming_deadlines,
    list_pending_items,
    search_by_text,
)
from app.services.vehicle_rules import evaluate_vehicle_rules
from app.services.embeddings import generate_embedding
from app.models.asset import AssetType

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL SCHEMAS — what the LLM sees (OpenAI/DeepSeek function-calling format)
# =============================================================================

TOOL_SAVE_VEHICLE = {
    "type": "function",
    "function": {
        "name": "save_vehicle",
        "description": "Guardar un vehículo del usuario. Lucho calcula automáticamente la fecha de matriculación, pico y placa, SOAT y RTV. Usar cuando el usuario menciona una placa de auto o moto ecuatoriana (formato ABC-1234 o ABC-123).",
        "parameters": {
            "type": "object",
            "properties": {
                "plate": {
                    "type": "string",
                    "description": "Placa del vehículo en formato ecuatoriano. Ej: PBC-1234, ABC-123.",
                },
                "brand": {
                    "type": "string",
                    "description": "Marca del vehículo. Ej: Toyota, Chevrolet, Kia.",
                },
                "model": {
                    "type": "string",
                    "description": "Modelo del vehículo. Ej: Corolla, Grand Vitara.",
                },
                "year": {
                    "type": "integer",
                    "description": "Año del vehículo. Ej: 2020.",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas adicionales sobre el vehículo.",
                },
            },
            "required": ["plate"],
        },
    },
}

TOOL_SAVE_DOCUMENT = {
    "type": "function",
    "function": {
        "name": "save_document",
        "description": "Guardar un documento personal del usuario: cédula de identidad, pasaporte, licencia de conducir, SOAT, garantía, factura, o cualquier documento con fecha de vencimiento.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_type": {
                    "type": "string",
                    "description": "Tipo de documento. Ej: cedula, pasaporte, licencia, soat, garantia, factura, otro.",
                },
                "name": {
                    "type": "string",
                    "description": "Nombre descriptivo del documento. Ej: 'Cédula de Patricio', 'SOAT del carro'.",
                },
                "expiry_date": {
                    "type": "string",
                    "description": "Fecha de vencimiento en formato YYYY-MM-DD, si aplica.",
                },
                "entity_name": {
                    "type": "string",
                    "description": "Nombre de la entidad emisora. Ej: 'Registro Civil', 'ANT', 'Seguros Equinoccial'.",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas adicionales.",
                },
            },
            "required": ["document_type", "name"],
        },
    },
}

TOOL_SAVE_EVENT = {
    "type": "function",
    "function": {
        "name": "save_event",
        "description": "Guardar un evento, cita, reunión, o recordatorio con fecha. El usuario será notificado automáticamente unos días antes.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título corto del evento. Ej: 'Cita dentista', 'Reunión banco'.",
                },
                "target_date": {
                    "type": "string",
                    "description": "Fecha del evento en formato YYYY-MM-DD. Calculá desde la fecha actual. 'mañana' = día siguiente, 'el lunes' = próximo lunes, 'en dos semanas' = +14 días.",
                },
                "description": {
                    "type": "string",
                    "description": "Descripción adicional del evento.",
                },
                "recurrence": {
                    "type": "string",
                    "description": "Si el evento se repite. Opciones: 'none', 'daily', 'weekly', 'monthly', 'yearly'.",
                },
            },
            "required": ["title", "target_date"],
        },
    },
}

TOOL_SAVE_LIST = {
    "type": "function",
    "function": {
        "name": "save_list",
        "description": "Guardar ítems en una lista (compras, tareas, pendientes, deseos). Si la lista no existe, se crea automáticamente.",
        "parameters": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista. Ej: 'compras', 'pendientes', 'supermaxi', 'deseos'.",
                },
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de ítems a agregar. Ej: ['leche', 'pan', 'huevos'].",
                },
                "quantity": {
                    "type": "string",
                    "description": "Cantidad si todos los ítems comparten la misma cantidad. Ej: '2 libras'.",
                },
            },
            "required": ["list_name", "items"],
        },
    },
}

TOOL_SAVE_NOTE = {
    "type": "function",
    "function": {
        "name": "save_note",
        "description": "Guardar una nota, idea, reflexión o información libre del usuario, organizada por tema.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Tema o categoría de la nota. Ej: 'ideas de negocio', 'recetas', 'salud', 'general'.",
                },
                "content": {
                    "type": "string",
                    "description": "Contenido completo de la nota.",
                },
            },
            "required": ["topic", "content"],
        },
    },
}

TOOL_SAVE_EXPENSE = {
    "type": "function",
    "function": {
        "name": "save_expense",
        "description": "Registrar un gasto compartido entre varias personas. Calcula automáticamente cuánto paga cada persona.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Descripción del gasto. Ej: 'Cena en La Parrilla'.",
                },
                "total_amount": {
                    "type": "number",
                    "description": "Monto total del gasto en dólares. Ej: 60.00.",
                },
                "participants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nombres de los participantes. Ej: ['Patricio', 'María', 'Juan'].",
                },
                "date": {
                    "type": "string",
                    "description": "Fecha del gasto en formato YYYY-MM-DD. Si no se menciona, usar la fecha actual.",
                },
            },
            "required": ["description", "total_amount", "participants"],
        },
    },
}

TOOL_SEARCH_DATA = {
    "type": "function",
    "function": {
        "name": "search_my_data",
        "description": "Buscar en TODOS los datos del usuario: vehículos, documentos, eventos, notas, listas, gastos. Usar cuando el usuario pregunta por algo que ya guardó (¿cuándo vence mi SOAT?, ¿qué tengo pendiente?, ¿cuál es mi pico y placa?, buscá mis notas de...).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Lo que el usuario está buscando, en sus propias palabras.",
                },
                "search_type": {
                    "type": "string",
                    "description": "Tipo de búsqueda. Opciones: 'deadlines' (vencimientos), 'pending' (pendientes), 'notes' (notas), 'vehicles' (vehículos), 'all' (todo). Si no estás seguro, usar 'all'.",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_GET_SUMMARY = {
    "type": "function",
    "function": {
        "name": "get_my_summary",
        "description": "Obtener un resumen rápido de todo lo que el usuario tiene: vehículos, próximos vencimientos, pendientes. Útil cuando el usuario pregunta '¿qué tengo?', 'resumen', '¿cómo voy?'.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_SEARCH_CONVERSATION = {
    "type": "function",
    "function": {
        "name": "search_conversation",
        "description": "Buscar en el historial de conversaciones del usuario. Usar cuando el usuario pregunta '¿qué te dije sobre...?', '¿recuerdas cuando hablamos de...?', 'busca en el chat...'.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Palabras o frase a buscar en el historial. Ej: 'carro', 'cita dentista', 'factura'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Cantidad máxima de resultados. Default: 5.",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_UPDATE_LAST = {
    "type": "function",
    "function": {
        "name": "update_last",
        "description": "Corregir o actualizar la última entidad que se guardó. Usar cuando el usuario dice 'no, era...', 'corregí...', 'cambiale...'.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Tipo de entidad a corregir: 'event', 'note', 'list', 'asset', 'expense'.",
                },
                "field": {
                    "type": "string",
                    "description": "Campo a modificar. Ej: 'title', 'target_date', 'content', 'plate'.",
                },
                "new_value": {
                    "type": "string",
                    "description": "Nuevo valor para el campo.",
                },
            },
            "required": ["entity_type", "field", "new_value"],
        },
    },
}

TOOL_CHECK_VEHICLE_INFO = {
    "type": "function",
    "function": {
        "name": "check_vehicle_info",
        "description": "Consultar información oficial de un vehículo ecuatoriano por placa: datos del SRI (marca, modelo, año, cilindraje, último año pagado), datos de matriculación (fechas, estado, cantón), y multas de tránsito ANT pendientes. Usar cuando el usuario pregunta por un vehículo específico o quiere saber si tiene multas.",
        "parameters": {
            "type": "object",
            "properties": {
                "plate": {
                    "type": "string",
                    "description": "Placa del vehículo sin guión. Ej: 'ABJ1245', 'PBC1234'.",
                },
            },
            "required": ["plate"],
        },
    },
}

# All available tools (exported for the agent loop)
ALL_TOOLS = [
    TOOL_SAVE_VEHICLE,
    TOOL_SAVE_DOCUMENT,
    TOOL_SAVE_EVENT,
    TOOL_SAVE_LIST,
    TOOL_SAVE_NOTE,
    TOOL_SAVE_EXPENSE,
    TOOL_SEARCH_DATA,
    TOOL_SEARCH_CONVERSATION,
    TOOL_GET_SUMMARY,
    TOOL_UPDATE_LAST,
    TOOL_CHECK_VEHICLE_INFO,
]

# Map tool names to their schemas for quick lookup
TOOL_SCHEMAS: dict[str, dict] = {
    t["function"]["name"]: t for t in ALL_TOOLS
}


# =============================================================================
# TOOL HANDLERS — deterministic Python code. LLM NEVER touches this.
# =============================================================================

async def handle_save_vehicle(session, user_id: str, args: dict) -> dict:
    """Save a vehicle and compute its rules (matriculation, pico y placa)."""
    from datetime import date
    import uuid

    plate = (args.get("plate") or "").upper().strip()
    if not plate:
        return {"success": False, "message": "Necesito la placa del vehículo."}

    # Build attributes
    attrs: dict[str, Any] = {"plate": plate}
    if args.get("brand"):
        attrs["brand"] = args["brand"]
    if args.get("model"):
        attrs["model"] = args["model"]
    if args.get("year"):
        attrs["year"] = args["year"]

    # Compute vehicle rules (pico y placa, matriculación, SOAT, RTV)
    today = date.today()
    try:
        rules = evaluate_vehicle_rules(plate, None, today)
        attrs.update({
            "last_digit": rules["last_digit"],
            "pico_y_placa_days": rules["pico_y_placa_days"],
            "next_matriculation": rules["next_matriculation"],
            "days_until_matriculation": rules["days_until_matriculation"],
        })
    except Exception as exc:
        logger.warning("Could not compute vehicle rules for %s: %s", plate, exc)

    name = f"{attrs.get('brand', '')} {attrs.get('model', '')} ({plate})".strip()
    if name == f"({plate})":
        name = plate

    try:
        asset = await persist_asset(
            session=session,
            user_id=uuid.UUID(user_id),
            asset_type="vehicle",
            name=name,
            attributes=attrs,
            notes=args.get("notes"),
        )
        return {
            "success": True,
            "message": f"Vehículo {plate} guardado.",
            "asset_id": str(asset.id),
            "plate": plate,
            "pico_y_placa_days": attrs.get("pico_y_placa_days", ""),
            "next_matriculation": attrs.get("next_matriculation", ""),
            "days_until_matriculation": attrs.get("days_until_matriculation", 0),
        }
    except Exception as exc:
        logger.exception("Failed to save vehicle: %s", exc)
        return {"success": False, "message": "No pude guardar el vehículo. ¿Intentamos de nuevo?"}


async def handle_save_document(session, user_id: str, args: dict) -> dict:
    """Save a personal document."""
    import uuid

    doc_type = (args.get("document_type") or "otro").lower().strip()
    name = (args.get("name") or "documento").strip()

    attrs: dict[str, Any] = {"document_type": doc_type}
    if args.get("expiry_date"):
        attrs["expiry_date"] = args["expiry_date"]
    if args.get("entity_name"):
        attrs["entity_name"] = args["entity_name"]

    try:
        await persist_asset(
            session=session,
            user_id=uuid.UUID(user_id),
            asset_type="document",
            name=name,
            attributes=attrs,
            notes=args.get("notes"),
        )
        expiry_msg = f", vence {attrs['expiry_date']}" if "expiry_date" in attrs else ""
        return {
            "success": True,
            "message": f"Documento '{name}' guardado{expiry_msg}.",
        }
    except Exception as exc:
        logger.exception("Failed to save document: %s", exc)
        return {"success": False, "message": "No pude guardar el documento."}


async def handle_save_event(session, user_id: str, args: dict) -> dict:
    """Save an event/reminder."""
    import uuid

    title = (args.get("title") or "evento").strip()
    target_date = args.get("target_date", "")
    recurrence = args.get("recurrence", "none")

    if not target_date:
        return {"success": False, "message": "Necesito saber la fecha del evento."}

    recurrence_rule = None
    if recurrence and recurrence != "none":
        recurrence_rule = {"freq": recurrence, "interval": 1}

    try:
        event = await persist_event(
            session=session,
            user_id=uuid.UUID(user_id),
            title=title,
            target_date=target_date,
            description=args.get("description"),
            certainty="certain",
            recurrence_rule=recurrence_rule,
        )
        recur_msg = f", se repite {recurrence}" if recurrence_rule else ""
        return {
            "success": True,
            "message": f"Evento '{title}' agendado para {target_date}{recur_msg}. Te recordaré antes.",
            "event_id": str(event.id),
            "target_date": target_date,
        }
    except Exception as exc:
        logger.exception("Failed to save event: %s", exc)
        return {"success": False, "message": "No pude guardar el evento."}


async def handle_save_list(session, user_id: str, args: dict) -> dict:
    """Save items to a list."""
    import uuid

    list_name = (args.get("list_name") or "general").strip()
    items = args.get("items") or []

    if not items:
        return {"success": False, "message": "Necesito al menos un ítem para la lista."}

    try:
        saved = await persist_list_items(
            session=session,
            user_id=uuid.UUID(user_id),
            list_name=list_name,
            items=items,
            quantity=args.get("quantity"),
        )
        return {
            "success": True,
            "message": f"{len(items)} ítem(s) agregado(s) a '{list_name}'.",
            "count": len(items),
            "list_name": list_name,
        }
    except Exception as exc:
        logger.exception("Failed to save list items: %s", exc)
        return {"success": False, "message": "No pude guardar los ítems."}


async def handle_save_note(session, user_id: str, args: dict) -> dict:
    """Save a note."""
    import uuid

    topic = (args.get("topic") or "general").strip()
    content = (args.get("content") or "").strip()

    if not content:
        return {"success": False, "message": "Necesito el contenido de la nota."}

    try:
        note = await persist_note(
            session=session,
            user_id=uuid.UUID(user_id),
            topic_name=topic,
            content=content,
        )
        return {
            "success": True,
            "message": f"Nota guardada en '{topic}'.",
            "note_id": str(note.id),
            "topic": topic,
        }
    except Exception as exc:
        logger.exception("Failed to save note: %s", exc)
        return {"success": False, "message": "No pude guardar la nota."}


async def handle_save_expense(session, user_id: str, args: dict) -> dict:
    """Save a shared expense."""
    import uuid

    description = (args.get("description") or "gasto").strip()
    total_amount = float(args.get("total_amount") or 0)
    participants = args.get("participants") or []

    if total_amount <= 0:
        return {"success": False, "message": "Necesito el monto del gasto."}
    if not participants:
        return {"success": False, "message": "Necesito saber entre cuántas personas."}

    per_person = total_amount / len(participants)

    try:
        expense = await persist_shared_expense(
            session=session,
            user_id=uuid.UUID(user_id),
            description=description,
            total_amount=total_amount,
            participants=participants,
            split_type="equal",
        )
        return {
            "success": True,
            "message": f"Gasto '{description}' registrado: ${total_amount:.2f} entre {len(participants)} = ${per_person:.2f} c/u.",
            "total": total_amount,
            "participants": len(participants),
            "per_person": round(per_person, 2),
        }
    except Exception as exc:
        logger.exception("Failed to save expense: %s", exc)
        return {"success": False, "message": "No pude guardar el gasto."}


async def handle_search_data(session, user_id: str, args: dict) -> dict:
    """Search all user data."""
    import uuid

    query = (args.get("query") or "").strip()
    search_type = (args.get("search_type") or "all").strip()

    if not query:
        return {"success": False, "message": "¿Qué querés que busque?", "results": []}

    uid = uuid.UUID(user_id)
    results_parts: list[str] = []
    found_items: list[dict] = []

    # ---- Vehicles ----
    if search_type in ("vehicles", "all"):
        from sqlalchemy import select
        from app.models.asset import Asset
        result = await session.execute(
            select(Asset).where(
                Asset.user_id == uid,
                Asset.asset_type == AssetType.vehicle,
                Asset.deleted_at.is_(None),
            )
        )
        vehicles = result.scalars().all()
        if vehicles:
            for v in vehicles:
                attrs = v.attributes or {}
                plate = attrs.get("plate", "?")
                pyp = attrs.get("pico_y_placa_days", "")
                matric = attrs.get("next_matriculation", "")
                lines = [f"🚗 {plate} — {v.name}"]
                if pyp:
                    lines.append(f"   Pico y placa: {pyp}")
                if matric:
                    lines.append(f"   Matriculación: {matric}")
                results_parts.append("\n".join(lines))
                found_items.append({"type": "vehicle", "plate": plate, "name": v.name})

    # ---- Pending items ----
    if search_type in ("pending", "all"):
        pending = await list_pending_items(session, uid)
        if pending:
            lines = ["📝 Pendientes:"]
            for p in pending[:10]:
                lines.append(f"   • [{p['list']}] {p['content']}")
                found_items.append({"type": "pending", "list": p["list"], "content": p["content"]})
            results_parts.append("\n".join(lines))

    # ---- Deadlines ----
    if search_type in ("deadlines", "all"):
        deadlines = await upcoming_deadlines(session, uid, days_ahead=90)
        if deadlines:
            lines = ["📅 Próximos vencimientos:"]
            for d in deadlines[:8]:
                emoji = "🔴" if d["days_left"] <= 7 else "🟡" if d["days_left"] <= 30 else "🟢"
                lines.append(f"   {emoji} {d['title']}: {d['target_date']} ({d['days_left']} días)")
                found_items.append({"type": "deadline", "title": d["title"], "date": d["target_date"], "days_left": d["days_left"]})
            results_parts.append("\n".join(lines))

    # ---- Text search (notes, lists) ----
    if search_type in ("notes", "all") and len(query) > 2:
        text_results = await search_by_text(session, uid, query, limit=5)
        if text_results:
            lines = ["💡 Encontrado:"]
            for t in text_results:
                preview = t["text"][:120]
                lines.append(f"   [{t['source']}] {preview}")
                found_items.append({"type": t["source"], "text": t["text"][:200]})
            results_parts.append("\n".join(lines))

    # ---- Semantic search ----
    if search_type == "all" and len(query) > 3:
        try:
            embedding = await generate_embedding(query)
            if embedding:
                semantic_results = await semantic_search(session, uid, embedding, top_k=5)
                if semantic_results:
                    for sr in semantic_results:
                        found_items.append({
                            "type": f"semantic_{sr['source']}",
                            "text": sr["text"][:200],
                            "similarity": sr["similarity"],
                        })
        except Exception as exc:
            logger.warning("Semantic search failed: %s", exc)

    if not found_items:
        return {
            "success": True,
            "message": "No encontré nada sobre eso. ¿Querés que lo guarde?",
            "results": [],
            "raw_data": "",
        }

    return {
        "success": True,
        "message": f"Encontré {len(found_items)} resultado(s).",
        "results": found_items,
        "raw_data": "\n\n".join(results_parts),
    }


async def handle_get_summary(session, user_id: str, args: dict) -> dict:
    """Get a quick summary of everything."""
    # Reuse search with type='all' but with an empty query approach
    return await handle_search_data(
        session, user_id,
        {"query": "resumen", "search_type": "all"}
    )


async def handle_update_last(session, user_id: str, args: dict) -> dict:
    """Update the last entity the user created."""
    import uuid
    from sqlalchemy import select, desc

    entity_type = (args.get("entity_type") or "").strip()
    field = (args.get("field") or "").strip()
    new_value = (args.get("new_value") or "").strip()

    if not entity_type or not field:
        return {"success": False, "message": "No sé qué corregir. ¿Me decís qué dato cambiar?"}

    uid = uuid.UUID(user_id)

    # Map entity types to models and their most recent query
    match entity_type:
        case "event":
            from app.models.event import Event
            result = await session.execute(
                select(Event).where(Event.user_id == uid).order_by(desc(Event.created_at)).limit(1)
            )
            entity = result.scalar_one_or_none()
            label = entity.title if entity else "evento"
        case "note":
            from app.models.topic import Note
            result = await session.execute(
                select(Note).join(Note.topic).where(Note.topic.has(user_id=uid)).order_by(desc(Note.created_at)).limit(1)
            )
            entity = result.scalar_one_or_none()
            label = "nota"
        case "list":
            from app.models.list import ListItem
            result = await session.execute(
                select(ListItem).join(ListItem.list).where(ListItem.list.has(user_id=uid)).order_by(desc(ListItem.created_at)).limit(1)
            )
            entity = result.scalar_one_or_none()
            label = "ítem"
        case "asset":
            from app.models.asset import Asset
            result = await session.execute(
                select(Asset).where(Asset.user_id == uid, Asset.deleted_at.is_(None)).order_by(desc(Asset.created_at)).limit(1)
            )
            entity = result.scalar_one_or_none()
            label = entity.name if entity else "activo"
        case _:
            return {"success": False, "message": "No encontré qué corregir. ¿Me das más detalles?"}

    if not entity:
        return {"success": False, "message": "No encontré nada reciente para corregir."}

    if not hasattr(entity, field):
        return {"success": False, "message": f"El campo '{field}' no existe en {label}."}

    try:
        old_val = getattr(entity, field)
        setattr(entity, field, new_value)
        await session.flush()
        return {
            "success": True,
            "message": f"Corregido: {field} de '{old_val}' a '{new_value}' en {label}.",
        }
    except Exception as exc:
        logger.exception("Failed to update entity: %s", exc)
        return {"success": False, "message": "No pude hacer la corrección."}


async def handle_check_vehicle_info(session, user_id: str, args: dict) -> dict:
    """Query external API for vehicle info (SRI, matriculation, fines)."""
    import httpx
    from app.config import settings

    plate = (args.get("plate") or "").upper().strip().replace("-", "")
    if not plate:
        return {"success": False, "message": "Necesito la placa para consultar."}

    url = f"{settings.VEHICLE_INFO_API_URL}{plate}"
    headers = {"Authorization": f"Bearer {settings.VEHICLE_INFO_API_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Vehicle API HTTP error for %s: %s", plate, exc)
        return {"success": False, "message": f"El servicio de consulta no está disponible. Intentá más tarde."}
    except Exception as exc:
        logger.exception("Vehicle API error for %s: %s", plate, exc)
        return {"success": False, "message": "No pude consultar la información del vehículo."}

    if not data.get("successful"):
        return {"success": False, "message": f"No encontré información para la placa {plate}. ¿Está bien escrita?"}

    info = data.get("data", {})

    # ---- Parse vehicle data ----
    web = info.get("infoWeb", {}).get("data", {})
    sri = info.get("infoSri", {}).get("datosBase", {})
    multas_rows = info.get("multasAnt", {}).get("rows", [])
    propietario = info.get("propietario", {}).get("data", {})

    vehicle_info = {
        "plate": web.get("licensePlate") or sri.get("numeroPlaca") or plate,
        "brand": web.get("brand") or sri.get("descripcionMarca", ""),
        "model": web.get("model") or sri.get("descripcionModelo", ""),
        "year": web.get("modelYear") or sri.get("anioAuto", ""),
        "engine_cc": web.get("engineCapacity") or sri.get("cilindraje", ""),
        "vehicle_class": web.get("vehicleClass", ""),
        "service_type": web.get("serviceType", ""),
        "status": web.get("vehicleStatus", ""),
        "canton": web.get("registrationCanton", ""),
        "purchase_date": web.get("purchaseDate", ""),
        "last_registration": web.get("lastRegistrationDate", ""),
        "registration_expiry": web.get("registrationExpiryDate", ""),
        "last_payment_year": web.get("lastPaymentYear") or sri.get("ultimoAnioPagado", ""),
        "last_inspection": web.get("inspectionDate", ""),
        "country": sri.get("descripcionPais", "ECUADOR"),
    }

    # ---- Parse fines ----
    fines = []
    for m in multas_rows:
        cells = m.get("cell", [])
        if len(cells) >= 10:
            fines.append({
                "id": cells[1] if len(cells) > 1 else "?",
                "entity": cells[2] if len(cells) > 2 else "?",
                "date": (cells[6][:10] if len(cells) > 6 and cells[6] else "?"),
                "description": cells[10] if len(cells) > 10 else "Multa de tránsito",
                "status": cells[12] if len(cells) > 12 else "pendiente",
            })

    return {
        "success": True,
        "vehicle": vehicle_info,
        "fines_count": len(fines),
        "fines": fines,
    }


async def handle_search_conversation(session, user_id: str, args: dict) -> dict:
    """Search the user's message history for past conversations."""
    import uuid as uuid_mod
    from sqlalchemy import select, desc, or_, String, cast
    from app.models.message import Message

    query = (args.get("query") or "").strip()
    limit = min(int(args.get("limit") or 5), 15)

    if not query:
        return {"success": False, "message": "¿Qué querés que busque en el historial?"}

    uid = uuid_mod.UUID(user_id)
    pattern = f"%{query}%"

    result = await session.execute(
        select(Message)
        .where(
            Message.user_id == uid,
            or_(
                Message.text.ilike(pattern),
                cast(Message.extraction_result, String).ilike(pattern),
            ),
        )
        .order_by(desc(Message.received_at))
        .limit(limit)
    )

    messages = list(result.scalars().all())

    if not messages:
        return {
            "success": True,
            "message": f"No encontré nada sobre '{query}' en nuestro historial.",
            "found": [],
        }

    found = []
    for m in messages:
        agent_reply = ""
        if m.extraction_result and isinstance(m.extraction_result, dict):
            agent_reply = m.extraction_result.get("agent_response", "")[:200]
        found.append({
            "date": m.received_at.strftime("%Y-%m-%d %H:%M") if m.received_at else "?",
            "user_said": (m.text or "")[:200],
            "lucho_replied": agent_reply,
        })

    return {
        "success": True,
        "message": f"Encontré {len(found)} mensaje(s) sobre '{query}'.",
        "found": found,
    }


# =============================================================================
# TOOL DISPATCHER — maps tool name to handler function
# =============================================================================

TOOL_HANDLERS: dict[str, Any] = {
    "save_vehicle": handle_save_vehicle,
    "save_document": handle_save_document,
    "save_event": handle_save_event,
    "save_list": handle_save_list,
    "save_note": handle_save_note,
    "save_expense": handle_save_expense,
    "search_my_data": handle_search_data,
    "get_my_summary": handle_get_summary,
    "update_last": handle_update_last,
    "check_vehicle_info": handle_check_vehicle_info,
    "search_conversation": handle_search_conversation,
}


async def execute_tool(session, user_id: str, tool_name: str, tool_args: dict) -> dict:
    """
    Execute a tool by name. Called by the agent loop when the LLM requests a tool call.

    Args:
        session: SQLAlchemy async session
        user_id: UUID string of the current user
        tool_name: Name of the tool to execute
        tool_args: Arguments extracted from the LLM's function call

    Returns:
        Dict with at least {'success': bool, 'message': str}
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        logger.warning("Unknown tool requested: %s", tool_name)
        return {"success": False, "message": f"No conozco la herramienta '{tool_name}'."}

    logger.info("Executing tool '%s' for user %s: %s", tool_name, user_id[:8], tool_args)
    try:
        result = await handler(session, user_id, tool_args)
        return result
    except Exception as exc:
        logger.exception("Tool '%s' failed: %s", tool_name, exc)
        return {"success": False, "message": "Tuve un error. ¿Intentamos de nuevo?"}
