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
        "description": "Guardar un documento personal del usuario: cédula de identidad, pasaporte, licencia de conducir, SOAT, garantía, factura, o cualquier documento con fecha de vencimiento. SIEMPRE pasá el file_key si viene de analyze_image o de un archivo adjunto.",
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
                "file_key": {
                    "type": "string",
                    "description": "Clave del archivo en MinIO. Viene del resultado de analyze_image o del mensaje [foto: X]. Formato: 'user_id/photo_123.jpg'. SIEMPRE incluir este campo si el usuario envió una foto.",
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
        "description": "Guardar un evento, cita, reunión, o recordatorio con fecha. El usuario será notificado automáticamente unos días antes. Si el usuario adjuntó una foto (receta médica, invitación, captura), pasá el file_key para vincularla.",
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
                "file_key": {
                    "type": "string",
                    "description": "Clave de foto en MinIO si el usuario adjuntó una imagen. Formato: 'user_id/photo_123.jpg'.",
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
        "description": "Guardar una nota, idea, reflexión o información libre del usuario, organizada por tema. Si el usuario adjuntó una foto, pasá el file_key para vincularla a la nota.",
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
                "file_key": {
                    "type": "string",
                    "description": "Clave de foto en MinIO si el usuario adjuntó una imagen. Formato: 'user_id/photo_123.jpg'.",
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

TOOL_ANALYZE_IMAGE = {
    "type": "function",
    "function": {
        "name": "analyze_image",
        "description": "Analizar una imagen o documento que el usuario envió y extraer datos estructurados. Usar cuando el usuario envía una foto de un documento (SOAT, factura, cédula, licencia, garantía, matrícula) y quiere que Lucho extraiga la información. El parámetro file_key viene del contexto del mensaje.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_key": {
                    "type": "string",
                    "description": "Clave del archivo en MinIO (viene en el mensaje del usuario como 'minio://...').",
                },
                "hint": {
                    "type": "string",
                    "description": "Pista del usuario sobre qué tipo de documento es. Ej: 'factura del súper', 'mi SOAT', 'la garantía de la lavadora'.",
                },
            },
            "required": ["file_key"],
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

TOOL_SAVE_PROJECT_TASK = {
    "type": "function",
    "function": {
        "name": "save_project_task",
        "description": "Guardar una tarea en un proyecto. Si el proyecto no existe, se crea automáticamente. Usar cuando el usuario menciona un proyecto y una tarea: 'para el proyecto X necesito hacer Y', 'agrega esto a mi proyecto Z'.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nombre del proyecto. Ej: 'casa nueva', 'tesis', 'evento boda'.",
                },
                "content": {
                    "type": "string",
                    "description": "Descripción de la tarea. Ej: 'contratar albañil', 'revisar catering'.",
                },
                "due_date": {
                    "type": "string",
                    "description": "Fecha límite en formato YYYY-MM-DD, si aplica.",
                },
            },
            "required": ["project_name", "content"],
        },
    },
}

TOOL_LIST_PROJECT_TASKS = {
    "type": "function",
    "function": {
        "name": "list_project_tasks",
        "description": "Listar las tareas de un proyecto o de todos los proyectos del usuario. Usar cuando el usuario pregunta '¿cómo va mi proyecto X?', '¿qué tengo pendiente del proyecto Y?', 'muéstrame mis proyectos'.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nombre del proyecto a consultar. Si no se especifica, lista todos los proyectos.",
                },
                "status": {
                    "type": "string",
                    "description": "Filtrar por estado: 'pending', 'done', o 'all'. Default: 'all'.",
                },
            },
            "required": [],
        },
    },
}

TOOL_COMPLETE_PROJECT_TASK = {
    "type": "function",
    "function": {
        "name": "complete_project_task",
        "description": "Marcar una tarea de proyecto como completada. Usar cuando el usuario dice 'ya terminé X del proyecto Y', 'marca como hecho Z'.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nombre del proyecto.",
                },
                "task_content": {
                    "type": "string",
                    "description": "Contenido de la tarea a marcar como completada (o parte del contenido para buscarla).",
                },
            },
            "required": ["project_name", "task_content"],
        },
    },
}

TOOL_SAVE_CONTACT = {
    "type": "function",
    "function": {
        "name": "save_contact",
        "description": "Guardar un contacto personal: nombre, teléfono, email, WhatsApp, relación (amigo, familia, colega). Usar cuando el usuario quiere guardar información de contacto de alguien.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre completo del contacto.",
                },
                "phone_number": {
                    "type": "string",
                    "description": "Número de teléfono. Formato internacional o local.",
                },
                "email": {
                    "type": "string",
                    "description": "Dirección de correo electrónico.",
                },
                "whatsapp_id": {
                    "type": "string",
                    "description": "Número de WhatsApp (si es distinto del teléfono).",
                },
                "relationship": {
                    "type": "string",
                    "description": "Tipo de relación: 'amigo', 'familia', 'colega', 'cliente', 'proveedor', etc.",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas adicionales: cumpleaños, dirección, empresa, etc.",
                },
            },
            "required": ["name"],
        },
    },
}

TOOL_LIST_CONTACTS = {
    "type": "function",
    "function": {
        "name": "list_contacts",
        "description": "Listar los contactos guardados. Usar cuando el usuario pregunta '¿qué contactos tengo?', 'buscame el teléfono de X', 'mis contactos'.",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Buscar por nombre o relación. Si no se especifica, lista todos.",
                },
                "relationship": {
                    "type": "string",
                    "description": "Filtrar por relación: 'amigo', 'familia', 'colega'.",
                },
            },
            "required": [],
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

TOOL_SEND_PHOTO = {
    "type": "function",
    "function": {
        "name": "send_photo",
        "description": "Enviar una foto O documento (PDF, DOC) al usuario. Funciona para cualquier tipo de archivo guardado. Usar cuando el usuario pide ver, descargar o recibir algo: 'pasame mi cédula', 'mostrame el SOAT', 'enseñame la factura', 'descargar el PDF', 'quiero ver el documento', 'mandame el archivo'. El file_key viene de los resultados de búsqueda.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_key": {
                    "type": "string",
                    "description": "Clave del archivo en MinIO (aplica a fotos JPG/PNG Y documentos PDF/DOC). Viene de los resultados de búsqueda como 'file_key'. Ej: 'user_id/photo_123.jpg' o 'user_id/doc_456_factura.pdf'.",
                },
                "caption": {
                    "type": "string",
                    "description": "Texto descriptivo para acompañar la foto. Ej: 'Tu cédula de identidad', 'SOAT del PBC-1234'.",
                },
            },
            "required": ["file_key"],
        },
    },
}

TOOL_WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Buscar CUALQUIER cosa en internet — sin restricciones de tema. Deportes, restaurantes, cultura, historia, trámites, noticias, LO QUE SEA. Es gratis. Usar siempre que el usuario pregunte algo que no está en sus datos personales. Respondé con los resultados en 1-2 líneas y ofrecé guardar algo relacionado.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Consulta en español. Ej: 'mejores restaurantes Cuenca Ecuador', 'capital de Francia', 'quién ganó el mundial 2026'.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Cantidad máxima de resultados. Default: 5, máximo: 8.",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_LIST_MY_VEHICLES = {
    "type": "function",
    "function": {
        "name": "list_my_vehicles",
        "description": "Mostrar los vehículos del usuario con datos clave: pico y placa, matriculación, SOAT, RTV. Usar cuando el usuario pregunta '¿qué carros tengo?', '¿cómo están mis vehículos?', o quiere ver información de sus vehículos guardados.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_ADD_MAINTENANCE = {
    "type": "function",
    "function": {
        "name": "add_maintenance",
        "description": "Registrar un mantenimiento de un vehículo: cambio de aceite, frenos, llantas, batería, general. Incluye costo, kilometraje, taller y fecha del mantenimiento. El usuario puede subir la factura como foto.",
        "parameters": {
            "type": "object",
            "properties": {
                "vehicle_id_or_plate": {
                    "type": "string",
                    "description": "ID del vehículo o placa para identificar cuál vehículo. Ej: 'PBC1234'.",
                },
                "maintenance_type": {
                    "type": "string",
                    "description": "Tipo de mantenimiento: oil_change, brakes, tires, battery, general, other.",
                    "enum": ["oil_change", "brakes", "tires", "battery", "general", "other"],
                },
                "description": {
                    "type": "string",
                    "description": "Descripción de qué se hizo.",
                },
                "cost": {
                    "type": "number",
                    "description": "Costo en USD.",
                },
                "mileage_km": {
                    "type": "integer",
                    "description": "Kilometraje actual del vehículo.",
                },
                "performed_at": {
                    "type": "string",
                    "description": "Fecha del mantenimiento en formato YYYY-MM-DD. Default: hoy.",
                },
                "performed_by": {
                    "type": "string",
                    "description": "Taller o mecánico que hizo el trabajo.",
                },
                "next_at": {
                    "type": "string",
                    "description": "Fecha sugerida para el próximo mantenimiento (YYYY-MM-DD).",
                },
                "next_mileage_km": {
                    "type": "integer",
                    "description": "Kilometraje sugerido para el próximo mantenimiento.",
                },
                "file_key": {
                    "type": "string",
                    "description": "Clave del archivo en MinIO si el usuario adjuntó foto de la factura.",
                },
            },
            "required": ["vehicle_id_or_plate", "maintenance_type"],
        },
    },
}

TOOL_LIST_MAINTENANCES = {
    "type": "function",
    "function": {
        "name": "list_maintenances",
        "description": "Mostrar el historial de mantenimientos de un vehículo. Usar cuando el usuario pregunta '¿qué mantenimientos le hice al carro?', '¿cuándo fue el último cambio de aceite?', o quiere ver el historial.",
        "parameters": {
            "type": "object",
            "properties": {
                "vehicle_id_or_plate": {
                    "type": "string",
                    "description": "ID del vehículo o placa. Ej: 'PBC1234'.",
                },
            },
            "required": ["vehicle_id_or_plate"],
        },
    },
}


# All available tools (exported for the agent loop)
ALL_TOOLS = [
    TOOL_SAVE_VEHICLE,
    TOOL_LIST_MY_VEHICLES,
    TOOL_ADD_MAINTENANCE,
    TOOL_LIST_MAINTENANCES,
    TOOL_SAVE_DOCUMENT,
    TOOL_SAVE_EVENT,
    TOOL_SAVE_LIST,
    TOOL_SAVE_NOTE,
    TOOL_SAVE_EXPENSE,
    TOOL_SEARCH_DATA,
    TOOL_SEARCH_CONVERSATION,
    TOOL_ANALYZE_IMAGE,
    TOOL_GET_SUMMARY,
    TOOL_SAVE_PROJECT_TASK,
    TOOL_LIST_PROJECT_TASKS,
    TOOL_COMPLETE_PROJECT_TASK,
    TOOL_UPDATE_LAST,
    TOOL_SAVE_CONTACT,
    TOOL_LIST_CONTACTS,
    TOOL_CHECK_VEHICLE_INFO,
    TOOL_SEND_PHOTO,
    TOOL_WEB_SEARCH,
]

# Map tool names to their schemas for quick lookup
TOOL_SCHEMAS: dict[str, dict] = {
    t["function"]["name"]: t for t in ALL_TOOLS
}


# =============================================================================
# TOOL HANDLERS — deterministic Python code. LLM NEVER touches this.
# =============================================================================

async def handle_save_vehicle(session, user_id: str, args: dict) -> dict:
    """Save a vehicle to the dedicated vehicles table (max 2 per user)."""
    from datetime import date
    import uuid as uuid_mod
    from app.models.vehicle import Vehicle

    plate = (args.get("plate") or "").upper().strip().replace("-", "")
    if not plate:
        return {"success": False, "message": "Necesito la placa del vehículo."}

    user_uuid = uuid_mod.UUID(user_id)

    # ---- Enforce max vehicles per user from subscription plan features ----
    from app.models.subscription import Subscription, SubscriptionStatus
    sub_result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_uuid)
        .where(Subscription.status.in_([SubscriptionStatus.trial, SubscriptionStatus.active]))
    )
    sub = sub_result.scalar_one_or_none()

    max_vehicles = 2  # default
    if sub and sub.plan_ref and sub.plan_ref.features:
        max_vehicles = sub.plan_ref.features.get("max_vehicles", 2)

    count_result = await session.execute(
        select(Vehicle).where(
            Vehicle.user_id == user_uuid,
            Vehicle.deleted_at.is_(None),
        )
    )
    existing_count = len(count_result.scalars().all())
    if existing_count >= max_vehicles:
        return {
            "success": False,
            "message": (
                f"Ya tenés {existing_count} vehículo(s) registrado(s). "
                f"Tu plan permite máximo {max_vehicles}. "
                "Si querés reemplazar uno, primero eliminalo y luego agregá el nuevo. "
                "Decime 'eliminar vehículo [placa]' y lo borro."
            ),
        }

    # ---- Check for duplicate plate ----
    dup_result = await session.execute(
        select(Vehicle).where(
            Vehicle.user_id == user_uuid,
            Vehicle.plate == plate,
            Vehicle.deleted_at.is_(None),
        )
    )
    if dup_result.scalar_one_or_none():
        return {
            "success": False,
            "message": f"El vehículo con placa {plate} ya está registrado. Si querés actualizarlo, decime 'actualizar vehículo {plate}'.",
        }

    # ---- Compute vehicle rules (pico y placa, matriculación) ----
    today = date.today()
    last_digit = None
    pyp_days = ""
    next_matric = None
    try:
        rules = evaluate_vehicle_rules(plate, None, today)
        last_digit = rules["last_digit"]
        pyp_days = rules["pico_y_placa_days"]
        next_matric = date.fromisoformat(rules["next_matriculation"])
    except Exception as exc:
        logger.warning("Could not compute vehicle rules for %s: %s", plate, exc)

    # ---- Create vehicle ----
    vehicle = Vehicle(
        user_id=user_uuid,
        plate=plate,
        brand=args.get("brand"),
        model=args.get("model"),
        year=args.get("year"),
        last_digit=last_digit,
        pico_y_placa_days=pyp_days,
        next_matriculation=next_matric,
        notes=args.get("notes"),
    )
    session.add(vehicle)
    await session.flush()

    # ---- Build response ----
    brand_model = ""
    if args.get("brand") and args.get("model"):
        brand_model = f"{args['brand']} {args['model']} "
    elif args.get("brand"):
        brand_model = f"{args['brand']} "

    pyp_info = f"\n• Pico y placa: {pyp_days}" if pyp_days else ""
    matric_info = f"\n• Próxima matriculación: {next_matric}" if next_matric else ""

    return {
        "success": True,
        "message": f"Vehículo {plate} guardado.",
        "vehicle": {
            "id": str(vehicle.id),
            "plate": plate,
            "brand": args.get("brand"),
            "model": args.get("model"),
            "year": args.get("year"),
            "pico_y_placa_days": pyp_days,
            "next_matriculation": str(next_matric) if next_matric else None,
            "last_digit": last_digit,
        },
    }


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
    if args.get("file_key"):
        attrs["file_key"] = args["file_key"]

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
        has_photo = " (con foto)" if "file_key" in attrs else ""
        return {
            "success": True,
            "message": f"Documento '{name}' guardado{expiry_msg}{has_photo}.",
            "file_key": attrs.get("file_key"),
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
    file_key = args.get("file_key", "")

    if not target_date:
        return {"success": False, "message": "Necesito saber la fecha del evento."}

    recurrence_rule = None
    if recurrence and recurrence != "none":
        recurrence_rule = {"freq": recurrence, "interval": 1}

    description = args.get("description") or ""
    if file_key:
        description = f"{description}\n[📸 foto: {file_key}]".strip()

    try:
        event = await persist_event(
            session=session,
            user_id=uuid.UUID(user_id),
            title=title,
            target_date=target_date,
            description=description,
            certainty="certain",
            recurrence_rule=recurrence_rule,
        )

        # Schedule ad-hoc reminder if the event has a specific time (not just a date)
        from app.services.scheduler import schedule_event_reminder
        if event.target_date.hour != 0 or event.target_date.minute != 0:
            schedule_event_reminder(str(event.id), event.target_date)

        recur_msg = f", se repite {recurrence}" if recurrence_rule else ""
        photo_msg = " (con foto adjunta)" if file_key else ""
        return {
            "success": True,
            "message": f"Evento '{title}' agendado para {target_date}{recur_msg}{photo_msg}. Te recordaré antes.",
            "event_id": str(event.id),
            "target_date": str(event.target_date),
            "file_key": file_key if file_key else None,
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
                file_key = attrs.get("file_key", "")
                lines = [f"🚗 {plate} — {v.name}"]
                if pyp:
                    lines.append(f"   Pico y placa: {pyp}")
                if matric:
                    lines.append(f"   Matriculación: {matric}")
                if file_key:
                    lines.append(f"   📸 foto: {file_key}")
                results_parts.append("\n".join(lines))
                item = {"type": "vehicle", "plate": plate, "name": v.name}
                if file_key:
                    item["file_key"] = file_key
                found_items.append(item)

    # ---- Documents ----
    if search_type in ("all",):
        from sqlalchemy import select
        from app.models.asset import Asset
        result = await session.execute(
            select(Asset).where(
                Asset.user_id == uid,
                Asset.asset_type.in_([AssetType.document, AssetType.insurance, AssetType.tax, AssetType.warranty]),
                Asset.deleted_at.is_(None),
            )
        )
        docs = result.scalars().all()
        if docs:
            for d in docs:
                attrs = d.attributes or {}
                doc_type = attrs.get("document_type", d.asset_type.value)
                expiry_date = attrs.get("expiry_date", "")
                file_key = attrs.get("file_key", "")
                lines = [f"📄 {d.name} ({doc_type})"]
                if expiry_date:
                    lines.append(f"   Vence: {expiry_date}")
                if file_key:
                    lines.append(f"   📸 foto: {file_key}")
                results_parts.append("\n".join(lines))
                item = {"type": "document", "document_type": doc_type, "name": d.name}
                if file_key:
                    item["file_key"] = file_key
                found_items.append(item)

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


async def handle_analyze_image(session, user_id: str, args: dict) -> dict:
    """Download image from MinIO and extract structured data with DeepSeek Vision."""
    from app.services import minio as minio_svc
    from app.services.vision import extract_document_data

    file_key = (args.get("file_key") or "").strip()
    hint = (args.get("hint") or "").strip()

    if not file_key:
        return {"success": False, "message": "No encuentro la foto. ¿Podés reenviarla?"}

    # Download from MinIO
    try:
        image_bytes = await minio_svc.download_file(file_key)
        if not image_bytes:
            return {"success": False, "message": "No pude acceder a la imagen. ¿Está bien guardada?"}
    except Exception as exc:
        logger.exception("MinIO download failed: %s", exc)
        return {"success": False, "message": "No pude descargar la imagen."}

    # Extract with DeepSeek Vision
    try:
        extracted = await extract_document_data(image_bytes)
    except Exception as exc:
        logger.exception("OCR extraction failed: %s", exc)
        return {"success": False, "message": "No pude leer el documento. ¿Está bien enfocado?"}

    if not extracted:
        return {"success": False, "message": "No pude extraer información de la imagen. ¿Podés describirla?"}

    doc_type = extracted.get("document_type", "documento")

    return {
        "success": True,
        "document_type": doc_type,
        "extracted": extracted,
        "file_key": file_key,
        "_save_hint": f"AHORA preguntale al usuario si quiere guardar este documento como '{doc_type}'. NO lo guardes sin confirmación. Si el usuario confirma, llamá a save_document con document_type='{doc_type}', name='{extracted.get('title', doc_type)}', file_key='{file_key}', y los datos extraídos.",
    }


async def handle_save_project_task(session, user_id: str, args: dict) -> dict:
    """Save a task to a project."""
    import uuid
    from app.services.persistence import persist_project_task

    project_name = (args.get("project_name") or "general").strip()
    content = (args.get("content") or "").strip()

    if not content:
        return {"success": False, "message": "¿Qué tarea querés agregar al proyecto?"}

    due_date = None
    if args.get("due_date"):
        try:
            from datetime import date as dt_date
            due_date = dt_date.fromisoformat(args["due_date"])
        except (ValueError, TypeError):
            pass

    try:
        task = await persist_project_task(
            session=session,
            user_id=uuid.UUID(user_id),
            project_name=project_name,
            content=content,
            due_date=due_date,
        )
        due_msg = f" para {args['due_date']}" if due_date else ""
        return {
            "success": True,
            "message": f"Tarea '{content[:60]}' agregada al proyecto '{project_name}'{due_msg}.",
            "task_id": str(task.id),
            "project_name": project_name,
        }
    except Exception as exc:
        logger.exception("Failed to save project task: %s", exc)
        return {"success": False, "message": "No pude guardar la tarea."}


async def handle_list_project_tasks(session, user_id: str, args: dict) -> dict:
    """List tasks for a project or all projects."""
    import uuid
    from sqlalchemy import select
    from app.models.project import Project, ProjectTask, TaskStatus

    uid = uuid.UUID(user_id)
    project_name = (args.get("project_name") or "").strip()
    status_filter = (args.get("status") or "all").strip()

    # Query projects
    query = select(Project).where(Project.user_id == uid, Project.status == "active")
    if project_name:
        query = query.where(Project.name == project_name)
    result = await session.execute(query.order_by(Project.name))
    projects = result.scalars().all()

    if not projects:
        return {"success": True, "message": "No tenés proyectos todavía. Decime 'crear proyecto X' y empezamos.", "projects": []}

    output = []
    for proj in projects:
        task_query = select(ProjectTask).where(ProjectTask.project_id == proj.id)
        if status_filter == "pending":
            task_query = task_query.where(ProjectTask.status == TaskStatus.pending)
        elif status_filter == "done":
            task_query = task_query.where(ProjectTask.status == TaskStatus.done)
        task_result = await session.execute(task_query.order_by(ProjectTask.created_at))
        tasks = task_result.scalars().all()

        proj_data = {
            "project_name": proj.name,
            "total_tasks": len(tasks),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.pending),
            "done": sum(1 for t in tasks if t.status == TaskStatus.done),
            "tasks": [
                {
                    "content": t.content,
                    "status": t.status.value if t.status else "pending",
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                }
                for t in tasks
            ],
        }
        output.append(proj_data)

    total_pending = sum(p["pending"] for p in output)
    return {
        "success": True,
        "message": f"Tenés {len(output)} proyecto(s) con {total_pending} tarea(s) pendiente(s).",
        "projects": output,
    }


async def handle_complete_project_task(session, user_id: str, args: dict) -> dict:
    """Mark a project task as completed."""
    import uuid
    from sqlalchemy import select
    from datetime import datetime, timezone
    from app.models.project import Project, ProjectTask, TaskStatus

    uid = uuid.UUID(user_id)
    project_name = (args.get("project_name") or "").strip()
    task_content = (args.get("task_content") or "").strip()

    if not project_name or not task_content:
        return {"success": False, "message": "Necesito saber el proyecto y la tarea."}

    # Find project
    result = await session.execute(
        select(Project).where(Project.user_id == uid, Project.name == project_name)
    )
    project = result.scalar_one_or_none()
    if not project:
        return {"success": False, "message": f"No encontré el proyecto '{project_name}'."}

    # Find task (partial match)
    pattern = f"%{task_content}%"
    result = await session.execute(
        select(ProjectTask).where(
            ProjectTask.project_id == project.id,
            ProjectTask.status == TaskStatus.pending,
            ProjectTask.content.ilike(pattern),
        ).limit(1)
    )
    task = result.scalar_one_or_none()
    if not task:
        return {"success": False, "message": f"No encontré una tarea pendiente que coincida con '{task_content}' en '{project_name}'."}

    task.status = TaskStatus.done
    task.completed_at = datetime.now(timezone.utc)
    await session.flush()

    return {
        "success": True,
        "message": f"✅ Tarea '{task.content[:60]}' completada en '{project_name}'.",
    }



async def handle_save_contact(session, user_id: str, args: dict) -> dict:
    """Save a contact."""
    import uuid
    from sqlalchemy import select
    from app.models.contact import Contact

    name = (args.get("name") or "").strip()
    if not name:
        return {"success": False, "message": "Necesito el nombre del contacto."}

    uid = uuid.UUID(user_id)
    result = await session.execute(
        select(Contact).where(Contact.user_id == uid, Contact.name == name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        if args.get("phone_number"):
            existing.phone_number = args["phone_number"]
        if args.get("email"):
            existing.email = args["email"]
        if args.get("whatsapp_id"):
            existing.whatsapp_id = args["whatsapp_id"]
        if args.get("relationship"):
            existing.relationship = args["relationship"]
        if args.get("notes"):
            existing.contact_notes = args["notes"]
        await session.flush()
        return {"success": True, "message": f"Contacto '{name}' actualizado."}

    contact = Contact(
        user_id=uid, name=name,
        phone_number=args.get("phone_number"),
        email=args.get("email"),
        whatsapp_id=args.get("whatsapp_id"),
        relationship=args.get("relationship"),
        contact_notes=args.get("notes"),
    )
    session.add(contact)
    await session.flush()
    rel_msg = f" ({args['relationship']})" if args.get("relationship") else ""
    return {"success": True, "message": f"Contacto '{name}'{rel_msg} guardado."}


async def handle_list_contacts(session, user_id: str, args: dict) -> dict:
    """List contacts, optionally filtered."""
    import uuid
    from sqlalchemy import select
    from app.models.contact import Contact

    uid = uuid.UUID(user_id)
    search = (args.get("search") or "").strip()
    relationship = (args.get("relationship") or "").strip()

    query = select(Contact).where(Contact.user_id == uid)
    if relationship:
        query = query.where(Contact.relationship == relationship)
    if search:
        query = query.where(Contact.name.ilike(f"%{search}%"))
    query = query.order_by(Contact.name)

    result = await session.execute(query)
    contacts = result.scalars().all()

    if not contacts:
        return {"success": True, "message": "No tenés contactos guardados. Decime 'guardá el contacto X' y empiezo.", "contacts": []}

    contact_list = []
    for c in contacts:
        info_parts = []
        if c.phone_number:
            info_parts.append(f"📱 {c.phone_number}")
        if c.email:
            info_parts.append(f"✉️ {c.email}")
        if c.whatsapp_id:
            info_parts.append(f"💬 WA: {c.whatsapp_id}")
        if c.relationship:
            info_parts.append(f"👥 {c.relationship}")
        contact_list.append({
            "name": c.name,
            "info": " | ".join(info_parts) if info_parts else "sin datos",
            "phone": c.phone_number,
            "email": c.email,
            "relationship": c.relationship,
            "notes": c.contact_notes,
        })

    return {
        "success": True,
        "message": f"Tenés {len(contacts)} contacto(s).",
        "contacts": contact_list,
    }


# =============================================================================
# TOOL DISPATCHER — maps tool name to handler function
# =============================================================================


async def handle_send_photo(session, user_id: str, args: dict) -> dict:
    """Validate photo exists in MinIO and return info so caller can send it."""
    from app.services import minio as minio_svc

    file_key = (args.get("file_key") or "").strip()
    if not file_key:
        return {"success": False, "message": "No encuentro esa foto. ¿Cuál querés ver?"}

    # Extract filename from key
    filename = file_key.split("/")[-1] if "/" in file_key else file_key
    caption = (args.get("caption") or "").strip()

    # Validate file exists in MinIO
    try:
        file_bytes = await minio_svc.download_file(file_key)
        if not file_bytes:
            return {"success": False, "message": f"No encontré el archivo '{filename}'. ¿Seguro que está guardado?"}
    except Exception as exc:
        logger.exception("MinIO check failed for send_photo: %s", exc)
        return {"success": False, "message": "No pude acceder al archivo."}

    return {
        "success": True,
        "message": f"Listo, aquí está: {caption or filename}",
        "file_key": file_key,
        "filename": filename,
        "caption": caption,
        "_action": "send_photo",
    }


async def handle_web_search(session, user_id: str, args: dict) -> dict:
    """Search the web for Ecuador-specific current information using DuckDuckGo."""
    from ddgs import DDGS

    query = (args.get("query") or "").strip()
    max_results = min(int(args.get("max_results") or 5), 8)

    if not query:
        return {"success": False, "message": "¿Qué querés que busque?"}

    logger.info("Web search query: %s (max %d results)", query, max_results)

    try:
        # DuckDuckGo search (runs in thread pool since DDGS is sync)
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))

        if not raw_results:
            return {
                "success": True,
                "message": f"No encontré resultados para '{query}'.",
                "results": [],
            }

        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", "")[:300],
                "url": r.get("href", ""),
            })

        return {
            "success": True,
            "message": f"Encontré {len(results)} resultado(s) web sobre '{query}'.",
            "results": results,
            "query": query,
        }

    except Exception as exc:
        logger.exception("Web search failed: %s", exc)
        return {
            "success": False,
            "message": "No pude buscar en internet ahora. ¿Intentamos más tarde?",
        }


async def handle_list_my_vehicles(session, user_id: str, args: dict) -> dict:
    """List all vehicles for the current user with key data."""
    import uuid as uuid_mod
    from app.models.vehicle import Vehicle

    result = await session.execute(
        select(Vehicle).where(
            Vehicle.user_id == uuid_mod.UUID(user_id),
            Vehicle.deleted_at.is_(None),
        )
    )
    vehicles = result.scalars().all()

    if not vehicles:
        return {
            "success": True,
            "message": "No tenés vehículos registrados todavía. Mandame la placa y te lo guardo.",
            "vehicles": [],
        }

    vehicle_list = []
    for v in vehicles:
        vehicle_list.append({
            "id": str(v.id),
            "plate": v.plate,
            "brand": v.brand,
            "model": v.model,
            "year": v.year,
            "color": v.color,
            "pico_y_placa_days": v.pico_y_placa_days,
            "next_matriculation": str(v.next_matriculation) if v.next_matriculation else None,
            "soat_expiry": str(v.soat_expiry) if v.soat_expiry else None,
            "rtv_expiry": str(v.rtv_expiry) if v.rtv_expiry else None,
            "notes": v.notes,
        })

    return {
        "success": True,
        "message": f"Tenés {len(vehicles)} vehículo(s) registrado(s).",
        "vehicles": vehicle_list,
    }


async def handle_add_maintenance(session, user_id: str, args: dict) -> dict:
    """Add a maintenance record for a vehicle."""
    from datetime import date
    import uuid as uuid_mod
    from app.models.vehicle import Vehicle, VehicleMaintenance, MaintenanceType

    vehicle_ref = (args.get("vehicle_id_or_plate") or "").upper().strip().replace("-", "")
    if not vehicle_ref:
        return {"success": False, "message": "¿A cuál vehículo le hiciste el mantenimiento? Decime la placa."}

    user_uuid = uuid_mod.UUID(user_id)

    # Find vehicle by id or plate
    try:
        vid = uuid_mod.UUID(vehicle_ref)
        result = await session.execute(
            select(Vehicle).where(Vehicle.id == vid, Vehicle.user_id == user_uuid)
        )
    except ValueError:
        result = await session.execute(
            select(Vehicle).where(
                Vehicle.plate == vehicle_ref,
                Vehicle.user_id == user_uuid,
                Vehicle.deleted_at.is_(None),
            )
        )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        return {
            "success": False,
            "message": f"No encontré el vehículo '{vehicle_ref}'. ¿Está bien escrita la placa?"
        }

    # Parse maintenance type
    mtype_str = (args.get("maintenance_type") or "other").lower().strip()
    try:
        mtype = MaintenanceType(mtype_str)
    except ValueError:
        mtype = MaintenanceType.other

    # Parse date
    performed_at_str = args.get("performed_at")
    performed_at = None
    if performed_at_str:
        try:
            performed_at = date.fromisoformat(performed_at_str)
        except (ValueError, TypeError):
            pass
    if not performed_at:
        performed_at = date.today()

    # Parse other date fields
    next_at = None
    if args.get("next_at"):
        try:
            next_at = date.fromisoformat(args["next_at"])
        except (ValueError, TypeError):
            pass

    maint = VehicleMaintenance(
        vehicle_id=vehicle.id,
        maintenance_type=mtype,
        description=args.get("description"),
        cost=args.get("cost"),
        mileage_km=args.get("mileage_km"),
        performed_at=performed_at,
        performed_by=args.get("performed_by"),
        next_at=next_at,
        next_mileage_km=args.get("next_mileage_km"),
        receipt_file_key=args.get("file_key"),
        notes=args.get("notes"),
    )
    session.add(maint)
    await session.flush()

    # Build friendly type name
    type_labels = {
        "oil_change": "cambio de aceite",
        "brakes": "frenos",
        "tires": "llantas",
        "battery": "batería",
        "general": "mantenimiento general",
        "other": "otro mantenimiento",
    }
    type_label = type_labels.get(mtype.value, mtype.value)

    cost_msg = f", ${args['cost']:.0f}" if args.get("cost") else ""
    km_msg = f", {args['mileage_km']} km" if args.get("mileage_km") else ""
    workshop_msg = f" en {args['performed_by']}" if args.get("performed_by") else ""

    return {
        "success": True,
        "message": (
            f"Registrado: {type_label} para {vehicle.plate}"
            f"{cost_msg}{km_msg}{workshop_msg}."
        ),
        "maintenance_id": str(maint.id),
    }


async def handle_list_maintenances(session, user_id: str, args: dict) -> dict:
    """List maintenance history for a vehicle."""
    import uuid as uuid_mod
    from app.models.vehicle import Vehicle, VehicleMaintenance

    vehicle_ref = (args.get("vehicle_id_or_plate") or "").upper().strip().replace("-", "")
    if not vehicle_ref:
        return {"success": False, "message": "¿De cuál vehículo querés ver los mantenimientos? Decime la placa."}

    user_uuid = uuid_mod.UUID(user_id)

    # Find vehicle
    try:
        vid = uuid_mod.UUID(vehicle_ref)
        result = await session.execute(
            select(Vehicle).where(Vehicle.id == vid, Vehicle.user_id == user_uuid)
        )
    except ValueError:
        result = await session.execute(
            select(Vehicle).where(
                Vehicle.plate == vehicle_ref,
                Vehicle.user_id == user_uuid,
                Vehicle.deleted_at.is_(None),
            )
        )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        return {
            "success": False,
            "message": f"No encontré el vehículo '{vehicle_ref}'."
        }

    maints_result = await session.execute(
        select(VehicleMaintenance)
        .where(VehicleMaintenance.vehicle_id == vehicle.id)
        .order_by(VehicleMaintenance.performed_at.desc())
        .limit(20)
    )
    maintenances = maints_result.scalars().all()

    if not maintenances:
        return {
            "success": True,
            "message": f"{vehicle.plate} no tiene mantenimientos registrados todavía.",
            "maintenances": [],
        }

    type_labels = {
        "oil_change": "🛢️ Cambio de aceite",
        "brakes": "🛑 Frenos",
        "tires": "🛞 Llantas",
        "battery": "🔋 Batería",
        "general": "🔧 General",
        "other": "📋 Otro",
    }

    maint_list = []
    for m in maintenances:
        maint_list.append({
            "id": str(m.id),
            "type": m.maintenance_type.value if m.maintenance_type else "other",
            "type_label": type_labels.get(m.maintenance_type.value if m.maintenance_type else "other", "Otro"),
            "description": m.description,
            "cost": m.cost,
            "mileage_km": m.mileage_km,
            "performed_at": str(m.performed_at) if m.performed_at else None,
            "performed_by": m.performed_by,
            "next_at": str(m.next_at) if m.next_at else None,
            "next_mileage_km": m.next_mileage_km,
            "receipt_file_key": m.receipt_file_key,
        })

    return {
        "success": True,
        "message": f"{vehicle.plate} tiene {len(maintenances)} mantenimiento(s) registrado(s).",
        "vehicle_plate": vehicle.plate,
        "maintenances": maint_list,
    }


TOOL_HANDLERS: dict[str, Any] = {
    "save_vehicle": handle_save_vehicle,
    "list_my_vehicles": handle_list_my_vehicles,
    "add_maintenance": handle_add_maintenance,
    "list_maintenances": handle_list_maintenances,
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
    "analyze_image": handle_analyze_image,
    "save_project_task": handle_save_project_task,
    "list_project_tasks": handle_list_project_tasks,
    "complete_project_task": handle_complete_project_task,
    "save_contact": handle_save_contact,
    "list_contacts": handle_list_contacts,
    "send_photo": handle_send_photo,
    "web_search": handle_web_search,
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
